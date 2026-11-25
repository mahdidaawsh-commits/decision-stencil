import ast
import hashlib
from itertools import product
import json
from pathlib import Path
import re

import pytest


CONTRACT = "contracts/decision_stencil.py"
SOURCE = "example/decision-stencil/" + "a" * 40 + "/fixtures/cache_reuse.json"
REPORT = Path("fixtures/cache_reuse.json").read_bytes()
DIGEST = hashlib.sha256(REPORT).hexdigest()
LABELS = {
    "000": "REJECT", "001": "REJECT", "010": "REJECT", "011": "REJECT",
    "100": "REJECT", "101": "UNKNOWN", "110": "ACCEPT", "111": "ACCEPT",
}


@pytest.fixture
def contract(direct_deploy):
    return direct_deploy(CONTRACT, sdk_version="v0.2.16")


def mock(vm, labels=LABELS, body=REPORT):
    vm.mock_web(re.escape("https://raw.githubusercontent.com/" + SOURCE), {"status": 200, "body": body})
    vm.mock_llm("DecisionStencil case adjudication", json.dumps(labels))


def test_immutable_stencil_and_all_lookup_paths(direct_vm, contract, direct_bob):
    mock(direct_vm)
    with direct_vm.prank(direct_bob):
        stencil_id = contract.publish(SOURCE, DIGEST)
    assert direct_vm.run_validator() is True
    stored = contract.get_stencil(stencil_id)
    assert (stored["depth"], stored["internal_nodes"]) == (3, 3)
    assert stored["labels"] == LABELS
    assert [contract.evaluate(stencil_id, bits)["outcome"] for bits in LABELS] == list(LABELS.values())
    assert contract.evaluate(stencil_id, "001")["questions"] == [{"feature": "digest_matches", "bit": "0"}]
    assert contract.evaluate(stencil_id, "101")["outcome"] == "UNKNOWN"
    with direct_vm.expect_revert("Stencil already published"):
        contract.publish(SOURCE, DIGEST)
    assert contract.get_stencil(stencil_id) == stored
    with direct_vm.expect_revert("Expected a binary feature vector"):
        contract.evaluate(stencil_id, "10X")


def test_label_change_alters_optimal_tree(direct_vm, contract):
    mock(direct_vm, {**LABELS, "101": "REJECT"})
    stencil_id = contract.publish(SOURCE, DIGEST)
    stored = contract.get_stencil(stencil_id)
    assert (stored["depth"], stored["internal_nodes"]) == (2, 2)
    assert contract.evaluate(stencil_id, "101")["outcome"] == "REJECT"


@pytest.mark.parametrize("replacement", ["ACCEPT", "REJECT"])
def test_validator_rejects_particular_changed_decision(direct_vm, contract, replacement):
    mock(direct_vm)
    contract.publish(SOURCE, DIGEST)
    direct_vm.clear_mocks()
    mock(direct_vm, {**LABELS, "101": replacement})
    assert direct_vm.run_validator() is False


def test_validator_refetches_committed_bytes(direct_vm, contract):
    mock(direct_vm)
    contract.publish(SOURCE, DIGEST)
    direct_vm.clear_mocks()
    mock(direct_vm, body=REPORT + b" ")
    assert direct_vm.run_validator() is False


@pytest.mark.parametrize("labels", [{"000": "REJECT"}, {**LABELS, "101": "PENDING"}, {**LABELS, "222": "ACCEPT"}])
def test_invalid_model_output_cannot_publish(direct_vm, contract, labels):
    mock(direct_vm, labels)
    with direct_vm.expect_revert("Case matrix acquisition or interpretation failed"):
        contract.publish(SOURCE, DIGEST)


def test_incomplete_matrix_cannot_publish(direct_vm, contract):
    data = json.loads(REPORT)
    del data["cases"]["101"]
    body = json.dumps(data).encode("utf-8")
    mock(direct_vm, body=body)
    with direct_vm.expect_revert("Case matrix acquisition or interpretation failed"):
        contract.publish(SOURCE, hashlib.sha256(body).hexdigest())


@pytest.mark.parametrize(("width", "alphabet"), [(2, ("ACCEPT", "REJECT", "UNKNOWN")), (3, ("ACCEPT", "REJECT"))])
def test_compiler_matches_exhaustive_tree_search(width, alphabet):
    source = ast.parse(Path(CONTRACT).read_text(encoding="utf-8"))
    compiler = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "compile_tree")
    namespace = {}
    exec(compile(ast.Module(body=[compiler], type_ignores=[]), CONTRACT, "exec"), namespace)
    compile_tree = namespace["compile_tree"]
    features = list("abcd"[:width])
    inputs = ["".join(bits) for bits in product("01", repeat=width)]

    def all_costs(cases, choices, labels):
        if len({labels[case] for case in cases}) == 1:
            return {(0, 0)}
        costs = set()
        for choice in choices:
            future = [index for index in choices if index != choice]
            zero = all_costs([case for case in cases if case[choice] == "0"], future, labels)
            one = all_costs([case for case in cases if case[choice] == "1"], future, labels)
            costs.update((1 + max(a[0], b[0]), 1 + a[1] + b[1]) for a, b in product(zero, one))
        return costs

    for labels in product(alphabet, repeat=len(inputs)):
        outcomes = dict(zip(inputs, labels))
        compiled = compile_tree(features, outcomes)
        assert (compiled["depth"], compiled["internal_nodes"]) == min(all_costs(inputs, range(width), outcomes))
        for bits, outcome in outcomes.items():
            node = compiled["tree"]
            while "test" in node:
                node = node["zero"] if bits[node["test"]] == "0" else node["one"]
            assert node["outcome"] == outcome
