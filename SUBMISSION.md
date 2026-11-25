# DecisionStencil

**Category** · Intelligent Contracts

DecisionStencil turns a complete set of documented policy cases into a compact decision tree. Builders can look up the recorded decision for any covered input and inspect the exact questions the tree used.

The leader and GenLayer validators independently fetch the full commit-pinned case matrix, verify its SHA-256 digest, and interpret each final disposition. Consensus requires exact agreement on every accept, reject, or unknown outcome. Those outcomes drive a deterministic compiler that minimizes worst-case questions and then internal nodes. Anyone can publish or query a stencil.

The synthetic StudioNet example compiled eight cache-reuse reviews into a tree with three internal nodes. It preserved an unresolved case as unknown. Changing that case to a denial reduces the minimum depth from three questions to two, which the direct tests verify. GenVM lint and 11 direct tests passed, including exhaustive comparison against 337 small decision tables. Read-only replay checked the deployed source, the complete stencil, and three finalized transactions, including an expected duplicate rejection.

- **Repository** · [Source, tests, and documentation](https://github.com/mahdidaawsh-commits/decision-stencil)
- **StudioNet Explorer** · [Deployed contract](https://explorer-studio.genlayer.com/address/0x8D39500944a35d970B55c31f2d70DD92AAEDF27F)
- **Proofs** · [Finalized receipts, stored tree, and query paths](https://github.com/mahdidaawsh-commits/decision-stencil/blob/main/proofs/studionet.json)
