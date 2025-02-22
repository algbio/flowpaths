import flowpaths as fp
import networkx as nx

def main():
    # Create a simple graph
    graph = nx.DiGraph()
    graph.graph["id"] = "simple_graph"
    graph.add_edge("0", "a", flow=6)
    graph.add_edge("0", "b", flow=7)
    graph.add_edge("a", "b", flow=2)
    graph.add_edge("a", "c", flow=4)
    graph.add_edge("b", "c", flow=9)
    graph.add_edge("c", "d", flow=6)
    graph.add_edge("c", "1", flow=7)
    graph.add_edge("d", "1", flow=6)

    # We create a Minimum Flow Decomposition solver with default settings,
    # by specifying that the flow value of each edge is in the attribute `flow` of the edges.
    mfd_model = fp.MinFlowDecomp(graph, flow_attr="flow")

    # We solve it
    mfd_model.solve()

    # We process its solution
    process_solution(mfd_model)

    # We solve again, by deactivating all optimizations, and 
    # setting the weights of the solution paths to int
    mfd_model_slow = fp.MinFlowDecomp(
        graph,
        flow_attr="flow",
        weight_type=int,
        optimize_with_safe_paths=False,
        optimize_with_safe_sequences=False,
        optimize_with_safe_zero_edges=False,
        optimize_with_greedy=False,
    )
    mfd_model_slow.solve()
    process_solution(mfd_model_slow)

def draw_graph(graph: nx.DiGraph, paths: list, weights: list, id:str):

    import matplotlib.pyplot as plt
    import pydot

    pydot_graph = nx.drawing.nx_pydot.to_pydot(graph)
    pydot_graph.set_graph_defaults(rankdir='LR')
    pydot_graph.set_graph_defaults(shape='rectangle')
    
    print("Hello")
    pydot_graph.get_node("a")[0].get_pos()
    pydot_graph.write_dot(f"{id}.dot")
    
    # Read the dot file and extract node positions
    pos = {}
    with open(f"{id}.dot", "r") as file:
        lines = file.readlines()
        for i, line in enumerate(lines):
            if "pos=" in line and "->" not in lines[i - 1]:
                node_id = lines[i - 1].split("[")[0].strip()
                print("node_id", node_id)
                pos_str = line.split("pos=")[1].split('"')[1]
                x, y = map(float, pos_str.split(","))
                pos[node_id] = (x, y)
    
    print(pos)
    
    # pydot_graph.write_png(f"{id}.png")

    # tmp_G = graph

    # g = pydot.Dot(graph_type="digraph")
    
    # print(pydot_graph.get_node("a")[0])

    # pos = nx.nx_pydot.pydot_layout(graph, prog="dot")

    print(pos)

    # # Draw nodes
    # for node, (x, y) in pos.items():
    #     plt.scatter(x, y, s=800, edgecolors="tab:gray", alpha=0.9, color="tab:blue", marker='.')
    #     plt.text(x, y + 4, str(node), fontsize=12, ha='center', va='center', color='black')

    options = {"edgecolors": "tab:gray", "node_size": 800, "alpha": 0.9}
    basic_line_width = 2.0
    nx.draw_networkx_nodes(graph, pos, nodelist=graph.nodes(), node_color="tab:blue", **options)
    nx.draw_networkx_edges(graph, pos, width=basic_line_width, alpha=0.5, arrowsize=2)
    

    # # Draw edges
    # for (u, v, data) in graph.edges(data=True):
    #     x1, y1 = pos[str(u)]
    #     x2, y2 = pos[str(v)]
    #     plt.plot([x1, x2], [y1, y2], color="tab:gray", alpha=0, linestyle='-', linewidth=basic_line_width)
    #     # Optionally, add arrowheads
    #     plt.arrow(x1, y1, x2 - x1, y2 - y1, head_width=1, head_length=1, fc='tab:gray', ec='tab:gray')

    # Draw paths
    # Sort paths by weight in decreasing order
    sorted_paths = sorted(zip(paths, weights), key=lambda x: x[1], reverse=True)
    total_weight = sum(weights)
    colors = ["tab:red", "tab:green", "tab:blue", "tab:orange", "tab:purple", "tab:brown"]
    separator = 2  # Smaller separator between paths
    previous_shift = basic_line_width  # Initial shift up
    linewidth = [0 for i in range(len(sorted_paths))]

    for i, (path, weight) in enumerate(sorted_paths):
        path_edges = list(zip(path[:-1], path[1:]))
        x_coords = []
        y_coords = []
        linewidth[i] = max(2,(weight / total_weight) * 30)  # Set linewidth proportional to the path weight as a percentage of the total weight
        print("linewidth", linewidth[i])
        for (u, v) in path_edges:
            x1, y1 = pos[str(u)]
            x2, y2 = pos[str(v)]
            x_coords.extend([x1, x2])
            y_coords.extend([y1, y2])
        plt.plot(x_coords, y_coords, color=colors[i % len(colors)], alpha=0.35, linestyle='-', linewidth=linewidth[i])
        print("previous_shift", previous_shift)
        previous_shift += linewidth[i]/8 + separator  # Shift up for the next path

    # nodes
    options = {"edgecolors": "tab:gray", "node_size": 800, "alpha": 0.9}
    # nx.draw_networkx_nodes(G, pos, nodelist=[0, 1, 2, 3], node_color="tab:red", **options)
    # nx.draw_networkx_nodes(G, pos, nodelist=[4, 5, 6, 7], node_color="tab:blue", **options)
    # nx.draw_networkx_nodes(tmp_G, pos, nodelist=tmp_G.nodes(), node_color="tab:blue", **options)



    # edges
    # nx.draw_networkx_edges(tmp_G, pos, width=1.0, alpha=0.5, connectionstyle="arc3,rad=0.1")
    # nx.draw_networkx_edges(
    #     tmp_G,
    #     pos,
    #     edgelist=[(0, 1), (1, 2), (2, 3), (3, 0)],
    #     width=15,
    #     alpha=0.5,
    #     edge_color="tab:red",
    # )
    # nx.draw_networkx_edges(
    #     tmp_G,
    #     pos,
    #     edgelist=[(0, 1), (1, 2), (2, 3), (3, 0)],
    #     width=5,
    #     alpha=0.5,
    #     edge_color="tab:blue",
    # )
    # nx.draw_networkx_edges(
    #     tmp_G,
    #     pos,
    #     edgelist=[(4, 5), (5, 6), (6, 7), (7, 4)],
    #     width=8,
    #     alpha=0.5,
    #     edge_color="tab:blue",
    # )


    # # some math labels
    # labels = {}
    # labels[0] = r"$a$"
    # labels[1] = r"$b$"
    # labels[2] = r"$c$"
    # labels[3] = r"$d$"
    # labels[4] = r"$\alpha$"
    # labels[5] = r"$\beta$"
    # labels[6] = r"$\gamma$"
    # labels[7] = r"$\delta$"
    # nx.draw_networkx_labels(tmp_G, pos, labels, font_size=22, font_color="whitesmoke")

    plt.tight_layout()
    plt.axis("off")
    plt.savefig(f"{id}.pdf")


def process_solution(model: fp.MinFlowDecomp):
    if model.is_solved:
        solution = model.get_solution()
        print(
            "Solution paths, weights, solve statistics: ",
            solution[0],
            solution[1],
            model.solve_statistics,
        )
        # model.draw_solution()
        # draw_graph(model.G, paths = solution[0], weights = solution[1], id = model.G.graph["id"])
    else:
        print("Model could not be solved.")

if __name__ == "__main__":
    main()