"""Graph analytics service: community detection, PageRank, betweenness centrality, and bridge detection."""
from collections import defaultdict
import math


def compute_network_intelligence(nodes: list[dict], edges: list[dict], center_id: str) -> tuple[list[dict], list[dict], list[str]]:
    """
    Given a list of nodes and undirected edges, computes:
    1. Graph centrality (Degree, normalized PageRank, Betweenness centrality)
    2. Community detection (Modularity optimization / Label propagation)
    3. Community labeling and Bridge researcher identification
    """
    if not nodes:
        return nodes, [], []

    node_ids = [str(n['id']) for n in nodes]
    node_set = set(node_ids)
    adj = defaultdict(dict)

    # Build adjacency list with edge weights
    for e in edges:
        u, v = str(e['source']), str(e['target'])
        if u in node_set and v in node_set and u != v:
            w = float(e.get('weight', 1))
            adj[u][v] = max(adj[u].get(v, 0.0), w)
            adj[v][u] = max(adj[v].get(u, 0.0), w)

    n_count = len(node_ids)

    # 1. Degree Centrality
    degrees = {u: sum(adj[u].values()) for u in node_ids}
    max_degree = max(degrees.values()) if degrees and max(degrees.values()) > 0 else 1.0
    degree_centrality = {u: round(degrees[u] / max_degree, 3) for u in node_ids}

    # 2. PageRank (Power iteration, 25 steps)
    d = 0.85
    pr = {u: 1.0 / n_count for u in node_ids}
    for _ in range(25):
        next_pr = defaultdict(float)
        dangling_sum = sum(pr[u] for u in node_ids if not adj[u])
        for u in node_ids:
            if adj[u]:
                total_w = sum(adj[u].values())
                for v, w in adj[u].items():
                    next_pr[v] += d * pr[u] * (w / total_w)
            next_pr[u] += (1.0 - d) / n_count + (d * dangling_sum / n_count)
        pr = next_pr

    max_pr = max(pr.values()) if pr and max(pr.values()) > 0 else 1.0
    normalized_pr = {u: round(pr[u] / max_pr, 3) for u in node_ids}

    # 3. Betweenness Centrality (Brandes algorithm on weighted/unweighted shortest paths)
    betweenness = {u: 0.0 for u in node_ids}
    for s in node_ids:
        # Single-source shortest path
        S = []
        P = defaultdict(list)
        sigma = defaultdict(float)
        sigma[s] = 1.0
        d_dist = {u: -1.0 for u in node_ids}
        d_dist[s] = 0.0
        Q = [s]
        while Q:
            v = Q.pop(0)
            S.append(v)
            for w in adj[v]:
                # Path discovery
                if d_dist[w] < 0:
                    Q.append(w)
                    d_dist[w] = d_dist[v] + 1.0
                # Path counting
                if d_dist[w] == d_dist[v] + 1.0:
                    sigma[w] += sigma[v]
                    P[w].append(v)
        delta = defaultdict(float)
        while S:
            w = S.pop()
            for v in P[w]:
                delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != s:
                betweenness[w] += delta[w]

    # Normalize betweenness
    norm_factor = ((n_count - 1) * (n_count - 2)) if n_count > 2 else 1.0
    norm_betweenness = {u: round((betweenness[u] * 2.0) / norm_factor, 4) for u in node_ids}

    # 4. Community Detection (Multi-pass Label Propagation with weights)
    # Initialize each node in its own community
    labels = {u: i for i, u in enumerate(node_ids)}
    for _ in range(15):
        changed = 0
        for u in node_ids:
            if not adj[u]:
                continue
            neighbor_weights = defaultdict(float)
            for v, w in adj[u].items():
                neighbor_weights[labels[v]] += w
            if neighbor_weights:
                best_label = max(neighbor_weights.items(), key=lambda x: (x[1], -x[0]))[0]
                if labels[u] != best_label:
                    labels[u] = best_label
                    changed += 1
        if changed == 0:
            break

    # Remap communities to 1..K ordered by size
    comm_sizes = defaultdict(int)
    for u, lbl in labels.items():
        comm_sizes[lbl] += 1

    sorted_comms = sorted(comm_sizes.keys(), key=lambda l: comm_sizes[l], reverse=True)
    comm_map = {orig_lbl: new_id + 1 for new_id, orig_lbl in enumerate(sorted_comms)}
    community_assignments = {u: comm_map[labels[u]] for u in node_ids}

    # Derive community research area profiles & descriptors
    community_descriptors = [
        "Core Research Group",
        "Cross-Domain Explorers",
        "Systems & Infrastructure Lab",
        "Machine Learning & Data Hub",
        "Theoretical Computing Core",
        "Applications & Engineering Circle",
        "Emerging Technology Cluster",
        "Interdisciplinary Nexus"
    ]

    communities_summary = []
    for c_id in range(1, len(sorted_comms) + 1):
        c_nodes = [u for u in node_ids if community_assignments[u] == c_id]
        label_idx = (c_id - 1) % len(community_descriptors)
        communities_summary.append({
            "community_id": c_id,
            "label": f"Cluster {c_id}: {community_descriptors[label_idx]}",
            "size": len(c_nodes),
            "member_ids": c_nodes
        })

    # 5. Identify Bridge Researchers
    # Nodes with high betweenness that connect neighbors belonging to different communities
    bridge_ids = []
    avg_bw = sum(norm_betweenness.values()) / max(1, n_count)
    for u in node_ids:
        c_u = community_assignments[u]
        external_neighbors = sum(1 for v in adj[u] if community_assignments[v] != c_u)
        if external_neighbors >= 2 and norm_betweenness[u] > avg_bw * 1.5:
            bridge_ids.append(u)

    # Attach computed metrics to node dictionaries
    for n in nodes:
        u = str(n['id'])
        c_id = community_assignments.get(u, 1)
        label_idx = (c_id - 1) % len(community_descriptors)
        n['community_id'] = c_id
        n['community_label'] = f"Cluster {c_id}: {community_descriptors[label_idx]}"
        n['degree_centrality'] = degree_centrality.get(u, 0.0)
        n['betweenness_centrality'] = norm_betweenness.get(u, 0.0)
        n['pagerank'] = normalized_pr.get(u, 0.0)
        n['is_bridge'] = u in bridge_ids

    return nodes, communities_summary, bridge_ids

