"""
The curated Toolbox: GeoLibre tools (ids from the engine's manifests) grouped for GEIDA users, plus GEIDA's own
tools written in Python (engine "geida"). Terrain and hydrology (slope, catchments, streams…) are analyses, not
Toolbox tools. Ids missing from the engine are left out at load (and logged).
"""
GEIDA_TOOLS = {
    "geida_dissolve": {
        "display_name": "Dissolve",
        "summary": "Merges features into one, or one per value of a field (e.g. all buffers into one area, or "
                   "districts into regions); counts how many features were merged.",
        "params": [
            {"name": "input", "data_kind": "vector", "io_role": "input", "required": True, "description": "Layer to dissolve."},
            {"name": "field", "data_kind": "string", "required": False,
             "description": "Optional field: one result per value. Leave empty to merge everything."},
            {"name": "output", "data_kind": "vector", "io_role": "output", "required": True, "description": "Dissolved layer."},
        ],
    },
    "geida_zonal_statistics": {
        "display_name": "Zonal statistics by polygon",
        "summary": "For each polygon, statistics of a raster's values inside it (count, mean, min, max, median, sum, "
                   "standard deviation); adds them to the polygons and returns a table.",
        "params": [
            {"name": "input", "data_kind": "raster", "io_role": "input", "required": True, "description": "Raster to summarise."},
            {"name": "zones", "data_kind": "vector", "io_role": "input", "required": True, "description": "Polygons (zones)."},
            {"name": "output", "data_kind": "vector", "io_role": "output", "required": True, "description": "Polygons with statistics."},
        ],
    },
}

CATEGORIES = [
    ("vector_overlay", "Vector: overlay", "layers", [
        "clip", "intersect", "union", "difference", "erase", "symmetrical_difference", "identity", "update",
        "spatial_join", "select_by_location", "summarize_within", "tabulate_intersection", "count_overlapping_features",
        "line_intersections", "line_polygon_clip", "polygon_neighbors", "apportion_polygon"]),
    ("vector_geometry", "Vector: geometry", "shapes", [
        "buffer_vector", "multiple_ring_buffer", "geida_dissolve", "merge_vectors", "centroid_vector",
        "representative_point_vector", "minimum_convex_hull", "concave_hull", "minimum_bounding_box",
        "minimum_bounding_circle", "minimum_bounding_envelope", "simplify_features", "smooth_vectors",
        "densify_features", "polygonize", "multipart_to_singlepart", "singlepart_to_multipart", "polygons_to_lines",
        "lines_to_polygons", "remove_polygon_holes", "eliminate_polygons", "split_with_lines", "split_vector_lines",
        "feature_vertices_to_points", "extract_nodes", "repair_geometry", "subdivide_polygon", "reproject_vector"]),
    ("vector_measure", "Vector: measure and summarise", "ruler", [
        "add_geometry_attributes", "polygon_area", "polygon_perimeter", "polygon_long_axis", "polygon_short_axis",
        "compactness_ratio", "elongation_ratio", "perimeter_area_ratio", "near", "generate_near_table",
        "summarize_nearby", "vector_summary_statistics", "summary_statistics", "list_unique_values"]),
    ("attributes", "Attributes and tables", "table", [
        "extract_by_attribute", "field_calculator", "add_field", "delete_field", "rename_field", "reclassify_field",
        "join_tables", "merge_table_with_csv", "sort_features", "split_by_attributes", "export_table_to_csv",
        "attribute_histogram"]),
    ("grids", "Grids and sampling", "grid", [
        "hexagonal_grid_from_vector_base", "rectangular_grid_from_vector_base", "vector_hex_binning",
        "random_points_in_polygon", "create_spatial_sampling_locations", "create_spatially_balanced_points",
        "generate_transects_along_lines", "voronoi_diagram", "tile_grid_polygons", "aggregate_points"]),
    ("vector_stats", "Spatial statistics (points and polygons)", "scatter", [
        "getis_ord_gi_star", "optimized_hot_spot_analysis", "global_morans_i", "local_morans_i_lisa",
        "nearest_neighbour_index", "median_center", "central_feature", "directional_distribution", "hdbscan",
        "group_by_proximity"]),
    ("network", "Networks and routing", "route", [
        "shortest_path_network", "network_service_area", "closest_facility_network", "location_allocation_network",
        "network_connected_components", "network_centrality_metrics", "build_network_topology",
        "snap_points_to_network"]),
    ("raster_stats", "Raster: statistics", "sigma", [
        "geida_zonal_statistics", "raster_summary_stats", "zonal_statistics", "zonal_histogram", "cross_tabulation",
        "extract_raster_values_at_points", "list_unique_values_raster", "quantiles",
        "raster_area"]),
    ("raster_math", "Raster: calculate and overlay", "calculator", [
        "raster_calculator", "add", "subtract", "multiply", "divide", "weighted_overlay", "weighted_sum",
        "fuzzy_overlay", "min_overlay", "max_overlay", "average_overlay", "cell_statistics", "conditional_evaluation",
        "greater_than", "less_than", "equal_to", "bool_and", "bool_or", "rescale_by_function"]),
    ("raster_reclass", "Raster: reclassify and mask", "filter", [
        "reclass", "reclass_equal_interval", "slice_raster", "clip_raster_to_polygon", "erase_polygon_from_raster",
        "set_nodata_value", "modify_nodata_value", "majority_filter", "clump", "filter_raster_features_by_area",
        "boundary_clean", "expand_shrink", "nibble"]),
    ("conversion", "Convert, resample and reproject", "repeat", [
        "raster_to_vector_polygons", "raster_to_vector_points", "raster_to_vector_lines", "vector_polygons_to_raster",
        "vector_lines_to_raster", "vector_points_to_raster", "resample", "reproject_raster", "mosaic",
        "aggregate_raster", "convert_nodata_to_zero", "new_raster_from_base_vector", "vector_convert"]),
    ("distance", "Distance and cost", "move", [
        "euclidean_distance", "euclidean_allocation", "cost_distance", "cost_allocation", "cost_pathway",
        "buffer_raster", "path_distance", "corridor"]),
    ("neighbourhood", "Neighbourhood and filters", "blend", [
        "focal_statistics", "block_statistics", "mean_filter", "median_filter", "standard_deviation_filter",
        "gaussian_filter", "line_density", "point_statistics"]),
    ("interpolation", "Interpolation and density", "spline", [
        "idw_interpolation", "natural_neighbour_interpolation", "ordinary_kriging", "tin_interpolation",
        "nearest_neighbour_interpolation", "radial_basis_function_interpolation", "heat_map"]),
    ("classification", "Classification and change", "sparkles", [
        "k_means_clustering", "random_forest_classification", "min_dist_classification", "otsu_thresholding",
        "post_classification_change", "image_difference_change_detection", "change_vector_analysis",
        "classification_accuracy_assessment"]),
    ("visibility", "Visibility", "eye", ["viewshed", "visibility_index"]),
]

# Corrections to the engine's manifests (GeoLibre 1.7.1), found by running every tool above: some value parameters
# are described as raster inputs, one input as an output, and two vector inputs as rasters.
_NUMBER = {"data_kind": "number", "io_role": None, "schema": {"kind": "scalar", "scalar": "float"}}
_TEXT = {"data_kind": "string", "io_role": None, "schema": {"kind": "string"}}
_BOOL = {"data_kind": "bool", "io_role": None, "schema": {"kind": "bool"}}
PARAM_OVERRIDES = {
    ("hexagonal_grid_from_vector_base", "base"): {"data_kind": "vector"},
    ("rectangular_grid_from_vector_base", "base"): {"data_kind": "vector"},
    ("rectangular_grid_from_vector_base", "width"): _NUMBER,
    ("rectangular_grid_from_vector_base", "height"): _NUMBER,
    ("rectangular_grid_from_vector_base", "x_origin"): _NUMBER,
    ("rectangular_grid_from_vector_base", "y_origin"): _NUMBER,
    ("weighted_overlay", "weights"): _TEXT,
    ("weighted_sum", "weights"): _TEXT,
    ("conditional_evaluation", "true"): _TEXT,
    ("conditional_evaluation", "false"): _TEXT,
    ("clip_raster_to_polygon", "maintain_dimensions"): _BOOL,
    ("filter_raster_features_by_area", "threshold"): _NUMBER,
    ("cost_pathway", "destination"): {"io_role": "input", "data_kind": "raster"},
}
# "cell_size" is a number in every tool, although some describe it as a raster input.
NUMBER_PARAMS = {"cell_size"}
