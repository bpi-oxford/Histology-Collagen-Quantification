import os
import tifffile

import networkx as nx
from skimage import measure

import argparse
from tqdm import tqdm

def is_valid_file_or_directory(path):
    """Check if the given path is a valid file or directory."""
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(f"Path '{path}' does not exist.")
    return path

def get_args():
    parser = argparse.ArgumentParser(prog="decon",
                                     description="WSI collagen segmentation from PSR deconvolved channel")
    parser.add_argument(
        "-i", "--input", 
        dest="input",
        help="Path to the input OME TIFF file",
        metavar="PATH",
        type=is_valid_file_or_directory,
        required=True
        )
    parser.add_argument(
        "-o", "--output", 
        dest="output",
        help="Path to the output file",
        metavar="PATH",
        required=True
        )

    return parser.parse_args()

def main(args):
    print("Reading label mask...")
    label = tifffile.imread(args.input).T
    
    # relabel the mask
    print("Relabeling label mask...")
    label_re = measure.label(label,connectivity=2)

    # extract region properties
    print("Computing region properties...")
    regions = measure.regionprops(label_re)

    # Create a NetworkX graph
    G = nx.Graph()

    # Add nodes with region information
    NODE_SUBSAMPLES = 1
    for region in tqdm(regions[::NODE_SUBSAMPLES],desc="Adding nodes from labels"):
        centroid = region.centroid
        G.add_node(region.label, 
                area=region.area, 
                pos=(centroid[1],centroid[0]),
                perimeter=region.perimeter, 
                eccentricity=region.eccentricity,
                )
        
    # # Compute distances and add edges based on the threshold
    # Set a distance threshold
    # distance_threshold = 20

    # pbar = tqdm(total=len(G.nodes())**2,desc="Computing")

    # for u in G.nodes():
    #     for v in G.nodes():
    #         if u != v:
    #             dist = np.linalg.norm(np.array(G.nodes[u]["pos"]) - np.array(G.nodes[v]["pos"]))
    #             if dist > 0 and dist <=distance_threshold:
    #                 G.add_edge(u, v,dist=dist)

    # export network
    G_ = G
    # Split and save as float attributes
    for node in G_.nodes:
        x, y = G_.nodes[node]['pos']
        G_.nodes[node]['x'] = float(x)
        G_.nodes[node]['y'] = float(y)

    for (n,d) in G_.nodes(data=True):
        del d["pos"]

    # os.makedirs(OUTPUT_DIR,exist_ok=True)
    nx.write_gexf(G_, args.output)

if __name__ == "__main__":
    args = get_args()
    main(args)