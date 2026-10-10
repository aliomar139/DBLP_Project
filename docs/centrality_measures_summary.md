# Centrality measures in network research

## What centrality measures tell us

A network is a set of nodes joined by links. In a coauthor network, each researcher is a node, and two researchers have a link if they wrote a paper together. A centrality measure gives each node a score. Different measures give high scores for different reasons: many direct links, short routes to others, a position between groups, or links to influential nodes.

Some networks have arrows. For example, a citation link points from the paper that cites another paper to the paper it cites. In this case, a measure can count links coming in or going out. In a weighted network, explain what the weight means. It may show a stronger connection or a longer distance. Also say how you handle nodes that cannot reach other nodes.

## Four commonly used measures

### 1. Degree centrality

**Definition.** Degree is the number of links attached to a node. In an unweighted, undirected network, `k_i = Σ_j A_ij`. A normalized score divides this number by `n − 1`, where `n` is the total number of nodes. In a directed network, in-degree counts links coming in, and out-degree counts links going out.

**Example.** If Maya has coauthored papers with four researchers, her degree is 4. Degree counts these direct links only. It does not count the links of those four researchers.

**Papers using it.** Freeman’s foundational review presents degree as one of the main centrality measures. Valente et al. compare degree with closeness, betweenness, and eigenvector centrality in 58 social networks. Kitsak et al. include degree in their study of influential spreaders.

### 2. Closeness centrality

**Definition.** A path is a route through links. The shortest-path distance is the number of links in the shortest route between two nodes. Closeness is higher when a node’s total shortest-path distance to the other nodes is smaller. In a connected network, `C_i = (n − 1) / Σ_{j ≠ i} d(i,j)`. Some authors use the inverse of the average distance instead. In one network, this changes the scores by a constant factor.

**Example.** Consider four nodes in a line: `A—B—C—D`. From B, the distances to A, C, and D are 1, 1, and 2. From A, the distances to B, C, and D are 1, 2, and 3. B has the smaller total distance, so B has higher closeness.

In a disconnected network, some nodes have no path to others. Harmonic closeness is one solution: it sums reciprocal distances and gives unreachable nodes a score of zero.

**Papers using it.** Freeman’s review presents closeness as a main centrality measure. Valente et al. examine it in social networks. Bullmore and Sporns discuss it among measures used to study biological and brain networks.

### 3. Betweenness centrality

**Definition.** Betweenness measures how often a node lies on shortest paths between other pairs of nodes: `B_i = Σ_{s ≠ i ≠ t} σ_st(i) / σ_st`. Here, `σ_st` is the number of shortest paths from `s` to `t`, and `σ_st(i)` is the number of those paths that pass through node `i`. Researchers use different formulas to normalize the score.

**Example.** In `A—B—C`, the shortest route from A to C passes through B. So B receives betweenness for this pair. A node with high betweenness may connect groups that otherwise have few links between them. The score assumes that movement follows shortest paths; it does not show that people actually use those routes.

**Papers using it.** Freeman introduced betweenness to study intermediary positions in social networks. Valente et al. compare it with other common measures. Kitsak et al. include it in their study of spreading influence.

### 4. Eigenvector centrality

**Definition.** Eigenvector centrality gives a node a high score when it connects to other high-scoring nodes. In matrix form, `A x = λ x`; the score vector is usually the principal eigenvector of the adjacency matrix. For directed or disconnected networks, researchers need to state which eigenvector and normalization they use.

**Example.** Imagine two researchers who each have three coauthors. The first researcher’s coauthors are highly connected; the second researcher’s coauthors have few other links. Eigenvector centrality can give the first researcher the higher score because of who their coauthors are.

**Papers using it.** Bonacich developed eigenvector-based centrality measures and extended them into a family of power measures. Valente et al. compare eigenvector centrality with degree, closeness, and betweenness. Yan and Ding use centrality measures, including eigenvector centrality, to identify important papers in a journal’s citation network.

## Five other measures

### 5. PageRank

**Definition.** PageRank scores nodes in a network with arrows. A node gains score from links pointing to it. A link from a high-scoring node counts more, and that node shares its contribution among its outgoing links. The calculation also includes random jumps. These jumps help when a node has no outgoing links.

**Example from research.** Brin, Page, Motwani, and Winograd introduced PageRank in a paper about a large web search engine. It ranks web pages using the links between pages. A link from an important page contributes more than a link from a less important page.

### 6. Katz centrality

**Definition.** A walk is a route that follows links and may pass through several nodes. Katz centrality counts walks of different lengths and gives less weight to longer walks: `x = α A x + β 1`, or `x = β(I − αA)⁻¹1` when the inverse exists and `α` is below the convergence bound. The baseline term `β 1` gives each node a starting score.

**Example from research.** Katz’s original status-index paper counted how many people chose a person and who those people were. It also reduced the influence passed through intermediaries. Katz centrality is useful when indirect connections matter, but their influence should decrease with each step.

### 7. k-core (coreness)

**Definition.** To find a k-core, repeatedly remove nodes that have fewer than `k` links to the remaining nodes. A node’s coreness is the highest `k` for which it stays in the k-core.

**Example.** If a node belongs to a 3-core, it is part of a group where every member has at least three links to other members. Higher coreness means a node sits deeper in a dense part of the network.

**Papers using it.** Kitsak et al. found that nodes in high k-shells were often more effective spreaders than nodes with the highest degree or betweenness in the networks they studied. Coreness is useful when studying how information or infection spreads.

### 8. Harmonic centrality

**Definition.** Harmonic centrality gives nearby nodes more weight than distant nodes. It sums the reciprocal shortest-path distances from a node to all others: `H_i = Σ_{j ≠ i} 1/d(i,j)`. An unreachable node adds zero. A normalized version divides the score by `n − 1`.

**Example.** A node two links away adds `1/2` to the score. A node four links away adds `1/4`. If there is no path to a node, that node adds zero. This lets researchers calculate a closeness-like score in disconnected networks.

**Papers using it.** Ortega and Eballe study harmonic centrality in several graph families. Researchers also use it as an alternative to ordinary closeness when comparing networks.

### 9. Information centrality

**Definition.** Information centrality estimates how a node affects the movement of information through a network. It considers many possible routes between nodes, not only the shortest route. In Stephenson and Zelen’s method, the score is based on changes in network information when a node is removed or treated as a source.

**Example from research.** Stephenson and Zelen introduced the measure and applied it to a social network of men diagnosed with AIDS and to a baboon colony. It can be useful when alternate routes matter. Since versions of the measure can differ, a paper should state which formula it uses.

## Choosing a measure

| Research question | Possible measures |
|---|---|
| Which nodes have the most direct links? | Degree, in-degree, out-degree |
| Which nodes can reach others in few steps? | Closeness; harmonic closeness for disconnected networks |
| Which nodes connect groups along shortest routes? | Betweenness |
| Which nodes connect to influential nodes? | Eigenvector centrality, PageRank, Katz centrality |
| Which nodes are part of a dense core? | k-core / coreness |
| How does a node affect information moving along different routes? | Information centrality |

When reporting centrality scores, explain how you built the network, what each link and weight means, which formula you used, and what you did with disconnected parts of the network. If your question involves different kinds of importance, use measures that describe those different roles.

## Selected references

- Freeman, L. C. (1977). “A set of measures of centrality based on betweenness.” *Sociometry*, 40(1), 35–41. [JSTOR](https://www.jstor.org/stable/3033543).
- Freeman, L. C. (1979). “Centrality in social networks: Conceptual clarification.” *Social Networks*, 1(3), 215–239. [DOI](https://doi.org/10.1016/0378-8733(78)90021-7).
- Bonacich, P. (1987). “Power and Centrality: A Family of Measures.” *American Journal of Sociology*, 92(5), 1170–1182. [DOI](https://doi.org/10.1086/228631).
- Valente, T. W., Coronges, K., Lakon, C., & Costenbader, E. (2008). “How Correlated Are Network Centrality Measures?” *Connections*, 28(1), 16–26. [Open access article](https://pmc.ncbi.nlm.nih.gov/articles/PMC2875682/).
- Bullmore, E., & Sporns, O. (2009). “Complex brain networks: graph theoretical analysis of structural and functional systems.” *Nature Reviews Neuroscience*, 10, 186–198. [Open access copy](https://pmc.ncbi.nlm.nih.gov/articles/PMC3621511/).
- Yan, E., & Ding, Y. (2010). “Identifying key papers within a journal via network centrality measures.” *Journal of Informetrics*, 4(3), 270–286. [Open access article](https://pmc.ncbi.nlm.nih.gov/articles/PMC7088853/).
- Brin, S., Page, L., Motwani, R., & Winograd, T. (1998). “The anatomy of a large-scale hypertextual Web search engine.” [Google Research publication page](https://research.google/pubs/the-anatomy-of-a-large-scale-hypertextual-web-search-engine/).
- Katz, L. (1953). “A new status index derived from sociometric analysis.” *Psychometrika*, 18, 39–43. [DOI](https://doi.org/10.1007/BF02289026).
- Kitsak, M., et al. (2010). “Identification of influential spreaders in complex networks.” *Nature Physics*, 6, 888–893. [Open paper](https://arxiv.org/abs/1001.5285).
- Stephenson, K., & Zelen, M. (1989). “Rethinking centrality: Methods and examples.” *Social Networks*, 11(1), 1–37. [DOI](https://doi.org/10.1016/0378-8733(89)90016-6).
- Ortega, J. M. E., & Eballe, R. G. (2021). “Harmonic Centrality in Some Graph Families.” [arXiv](https://arxiv.org/abs/2111.12239).

> Related reference: Costenbader and Valente (2003), “The stability of centrality measures when networks are sampled,” tests how sampling affects 11 centrality measures. [DOI](https://doi.org/10.1016/S0378-8733(03)00012-1).
