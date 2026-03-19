# =============================================================================
# Spatial Morphogen Analysis for Media Change Protocol Generation
# Analyzes spatial transcriptomics data to identify differentially expressed
# secreted morphogens and generates media change CSV files
# =============================================================================

library(Seurat)
library(ggplot2)
library(dplyr)
library(tidyr)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Input files

RDS_FILE <- "C:\\Users\\David Sachs\\Downloads\\cs7_stereo_all_data.rds"
SPATIAL_META_FILE <- "C:\\Users\\David Sachs\\Downloads\\cs7_spatial_meta.csv"

# Output directory
OUTPUT_DIR <- "C:\\Users\\David Sachs\\Documents\\opentrons_api\\morphogen_outputs"
dir.create(OUTPUT_DIR, showWarnings = FALSE, recursive = TRUE)

# Known secreted morphogens (curated list for early embryonic development)
SECRETED_MORPHOGENS <- c(
  # TGF-beta/Activin/Nodal family
  "NODAL", "INHBA", "INHBB", "GDF1", "GDF3", "LEFTY1", "LEFTY2",
  "BMP2", "BMP4", "BMP5", "BMP6", "BMP7", "BMP8A", "BMP8B", "BMP10",
  "GDF5", "GDF6", "GDF7", "GDF9", "GDF10", "GDF11", "GDF15",
  "TGFB1", "TGFB2", "TGFB3", "MSTN", "AMH",

  # WNT family
  "WNT1", "WNT2", "WNT2B", "WNT3", "WNT3A", "WNT4", "WNT5A", "WNT5B",
  "WNT6", "WNT7A", "WNT7B", "WNT8A", "WNT8B", "WNT9A", "WNT9B",
  "WNT10A", "WNT10B", "WNT11", "WNT16",

  # WNT antagonists
  "DKK1", "DKK2", "DKK3", "DKK4", "SFRP1", "SFRP2", "SFRP4", "SFRP5",
  "WIF1", "CER1", "FRZB",

  # FGF family
  "FGF1", "FGF2", "FGF3", "FGF4", "FGF5", "FGF6", "FGF7", "FGF8",
  "FGF9", "FGF10", "FGF12", "FGF13", "FGF14", "FGF16", "FGF17",
  "FGF18", "FGF19", "FGF20", "FGF21", "FGF22", "FGF23",

  # Hedgehog family
  "SHH", "IHH", "DHH",

  # BMP antagonists
"NOG", "CHRD", "GREM1", "GREM2", "FST", "FSTL1", "FSTL3",
  "TWSG1", "NBL1",

  # Retinoic acid related
  "CYP26A1", "CYP26B1", "CYP26C1", "ALDH1A1", "ALDH1A2", "ALDH1A3",
  "RBP4", "CRABP1", "CRABP2",

  # Other important morphogens/signaling molecules
  "VEGFA", "VEGFB", "VEGFC", "VEGFD", "PGF",
  "PDGFA", "PDGFB", "PDGFC", "PDGFD",
  "EGF", "TGFA", "AREG", "EREG", "BTC", "HBEGF",
  "IGF1", "IGF2", "IGFBP1", "IGFBP2", "IGFBP3",
  "NRG1", "NRG2", "NRG3", "NRG4",
  "GDNF", "NRTN", "ARTN", "PSPN",
  "NGF", "BDNF", "NTF3", "NTF4",
  "LIF", "CNTF", "CTF1", "OSM",
  "EPO", "THPO", "CSF1", "CSF2", "CSF3",
  "IL6", "IL11"
)

# Number of concentration levels for plate layout
N_CONCENTRATION_LEVELS <- 4

# =============================================================================
# LOAD DATA
# =============================================================================

cat("Loading Seurat object...\n")
seurat_obj <- readRDS(RDS_FILE)

cat("Object loaded. Dimensions:", dim(seurat_obj), "\n")
cat("Assays:", Assays(seurat_obj), "\n")

# Check if spatial metadata exists
if (file.exists(SPATIAL_META_FILE)) {
  spatial_meta <- read.csv(SPATIAL_META_FILE)
  cat("Spatial metadata loaded:", nrow(spatial_meta), "cells\n")
}

# =============================================================================
# STANDARD QC AND PREPROCESSING
# =============================================================================

cat("\n=== QC and Preprocessing ===\n")

# Calculate QC metrics if not already present
if (!"percent.mt" %in% colnames(seurat_obj@meta.data)) {
  seurat_obj[["percent.mt"]] <- PercentageFeatureSet(seurat_obj, pattern = "^MT-")
}

if (!"nCount_RNA" %in% colnames(seurat_obj@meta.data)) {
  seurat_obj$nCount_RNA <- colSums(GetAssayData(seurat_obj, slot = "counts"))
}

if (!"nFeature_RNA" %in% colnames(seurat_obj@meta.data)) {
  seurat_obj$nFeature_RNA <- colSums(GetAssayData(seurat_obj, slot = "counts") > 0)
}

# QC Plots
pdf(file.path(OUTPUT_DIR, "QC_plots.pdf"), width = 12, height = 4)
VlnPlot(seurat_obj, features = c("nFeature_RNA", "nCount_RNA", "percent.mt"), ncol = 3)
dev.off()

# Filter cells (adjust thresholds as needed based on your data)
cat("Cells before filtering:", ncol(seurat_obj), "\n")
# Uncomment and adjust these thresholds based on your QC plots:
# seurat_obj <- subset(seurat_obj,
#                      subset = nFeature_RNA > 200 &
#                               nFeature_RNA < 7500 &
#                               percent.mt < 20)
cat("Cells after filtering:", ncol(seurat_obj), "\n")

# =============================================================================
# NORMALIZATION AND FEATURE SELECTION
# =============================================================================

cat("\n=== Normalization ===\n")

# Check if already normalized
if (!"data" %in% names(seurat_obj@assays$RNA@layers) &&
    max(GetAssayData(seurat_obj, slot = "data")) == max(GetAssayData(seurat_obj, slot = "counts"))) {
  seurat_obj <- NormalizeData(seurat_obj, normalization.method = "LogNormalize", scale.factor = 10000)
  cat("Normalization complete\n")
} else {
  cat("Data appears already normalized\n")
}

cat("\n=== Finding Variable Features ===\n")
seurat_obj <- FindVariableFeatures(seurat_obj, selection.method = "vst", nfeatures = 2000)

# Plot variable features
top10 <- head(VariableFeatures(seurat_obj), 10)
pdf(file.path(OUTPUT_DIR, "variable_features.pdf"), width = 10, height = 6)
plot1 <- VariableFeaturePlot(seurat_obj)
plot2 <- LabelPoints(plot = plot1, points = top10, repel = TRUE)
print(plot2)
dev.off()

# =============================================================================
# SCALING AND DIMENSIONAL REDUCTION
# =============================================================================

cat("\n=== Scaling ===\n")
all_genes <- rownames(seurat_obj)
seurat_obj <- ScaleData(seurat_obj, features = all_genes)

cat("\n=== PCA ===\n")
seurat_obj <- RunPCA(seurat_obj, features = VariableFeatures(seurat_obj))

# Elbow plot
pdf(file.path(OUTPUT_DIR, "elbow_plot.pdf"), width = 8, height = 6)
ElbowPlot(seurat_obj, ndims = 50)
dev.off()

cat("\n=== UMAP ===\n")
seurat_obj <- FindNeighbors(seurat_obj, dims = 1:30)
seurat_obj <- FindClusters(seurat_obj, resolution = 0.5)
seurat_obj <- RunUMAP(seurat_obj, dims = 1:30)

# UMAP plot
pdf(file.path(OUTPUT_DIR, "UMAP_clusters.pdf"), width = 10, height = 8)
DimPlot(seurat_obj, reduction = "umap", label = TRUE)
dev.off()

# =============================================================================
# SPATIAL DIFFERENTIAL EXPRESSION ANALYSIS
# =============================================================================

cat("\n=== Spatial Differential Expression ===\n")

# Check for spatial coordinates
has_spatial <- FALSE
spatial_coords <- NULL

# Try different ways to get spatial coordinates
if ("spatial" %in% names(seurat_obj@reductions)) {
  spatial_coords <- Embeddings(seurat_obj, "spatial")
  has_spatial <- TRUE
  cat("Found spatial coordinates in reductions\n")
} else if ("x" %in% colnames(seurat_obj@meta.data) && "y" %in% colnames(seurat_obj@meta.data)) {
  spatial_coords <- seurat_obj@meta.data[, c("x", "y")]
  has_spatial <- TRUE
  cat("Found spatial coordinates in metadata (x, y)\n")
} else if ("spatial_x" %in% colnames(seurat_obj@meta.data)) {
  spatial_coords <- seurat_obj@meta.data[, c("spatial_x", "spatial_y")]
  has_spatial <- TRUE
  cat("Found spatial coordinates in metadata (spatial_x, spatial_y)\n")
} else if (exists("spatial_meta") && nrow(spatial_meta) > 0) {
  # Try to merge spatial metadata
  cat("Attempting to use external spatial metadata\n")
  has_spatial <- TRUE
}

# Find spatially variable genes
spatially_variable_genes <- NULL

if (has_spatial && !is.null(spatial_coords)) {
  cat("Analyzing spatial variability...\n")

  # Add spatial coordinates to metadata
  seurat_obj$spatial_x <- spatial_coords[, 1]
  seurat_obj$spatial_y <- spatial_coords[, 2]

  # Method 1: Correlation with spatial coordinates
  # Get normalized expression data
  expr_data <- GetAssayData(seurat_obj, slot = "data")

  # Calculate correlation with x and y coordinates for each gene
  spatial_correlations <- data.frame(
    gene = rownames(expr_data),
    cor_x = NA,
    cor_y = NA,
    p_x = NA,
    p_y = NA
  )

  cat("Calculating spatial correlations...\n")
  for (i in seq_len(nrow(expr_data))) {
    if (i %% 1000 == 0) cat("  Processed", i, "genes\n")

    gene_expr <- as.numeric(expr_data[i, ])

    # Only test if gene is expressed in enough cells
    if (sum(gene_expr > 0) > 10) {
      test_x <- cor.test(gene_expr, seurat_obj$spatial_x, method = "spearman")
      test_y <- cor.test(gene_expr, seurat_obj$spatial_y, method = "spearman")

      spatial_correlations$cor_x[i] <- test_x$estimate
      spatial_correlations$cor_y[i] <- test_y$estimate
      spatial_correlations$p_x[i] <- test_x$p.value
      spatial_correlations$p_y[i] <- test_y$p.value
    }
  }

  # Calculate overall spatial variability score
  spatial_correlations <- spatial_correlations %>%
    mutate(
      max_abs_cor = pmax(abs(cor_x), abs(cor_y), na.rm = TRUE),
      min_p = pmin(p_x, p_y, na.rm = TRUE),
      spatial_score = max_abs_cor * (-log10(min_p + 1e-300))
    ) %>%
    filter(!is.na(spatial_score)) %>%
    arrange(desc(spatial_score))

  spatially_variable_genes <- spatial_correlations

  # Save full results
  write.csv(spatial_correlations,
            file.path(OUTPUT_DIR, "all_spatial_correlations.csv"),
            row.names = FALSE)

} else {
  cat("No spatial coordinates found. Using cluster-based differential expression.\n")

  # Find markers for each cluster as alternative
  all_markers <- FindAllMarkers(seurat_obj, only.pos = TRUE, min.pct = 0.25, logfc.threshold = 0.25)

  spatially_variable_genes <- all_markers %>%
    group_by(gene) %>%
    summarise(
      max_logfc = max(avg_log2FC),
      min_p = min(p_val_adj),
      n_clusters = n(),
      spatial_score = max_logfc * n_clusters
    ) %>%
    arrange(desc(spatial_score))

  write.csv(all_markers, file.path(OUTPUT_DIR, "cluster_markers.csv"), row.names = FALSE)
}

# =============================================================================
# IDENTIFY IMPORTANT SECRETED MORPHOGENS
# =============================================================================

cat("\n=== Identifying Important Secreted Morphogens ===\n")

# Get genes present in the dataset
genes_in_data <- rownames(seurat_obj)

# Find which morphogens are present
morphogens_present <- intersect(SECRETED_MORPHOGENS, genes_in_data)
cat("Secreted morphogens found in dataset:", length(morphogens_present), "of",
    length(SECRETED_MORPHOGENS), "\n")
cat("Morphogens present:", paste(morphogens_present, collapse = ", "), "\n\n")

# Filter spatial results for morphogens
if (!is.null(spatially_variable_genes)) {
  morphogen_spatial <- spatially_variable_genes %>%
    filter(gene %in% morphogens_present) %>%
    arrange(desc(spatial_score))

  cat("Spatially variable morphogens:\n")
  print(head(morphogen_spatial, 20))

  write.csv(morphogen_spatial,
            file.path(OUTPUT_DIR, "spatially_variable_morphogens.csv"),
            row.names = FALSE)
}

# Get expression statistics for morphogens
morphogen_expr <- GetAssayData(seurat_obj, slot = "data")[morphogens_present, , drop = FALSE]
morphogen_stats <- data.frame(
  gene = morphogens_present,
  mean_expr = rowMeans(morphogen_expr),
  pct_expressing = rowMeans(morphogen_expr > 0) * 100,
  max_expr = apply(morphogen_expr, 1, max)
) %>%
  arrange(desc(mean_expr))

write.csv(morphogen_stats,
          file.path(OUTPUT_DIR, "morphogen_expression_stats.csv"),
          row.names = FALSE)

# =============================================================================
# GENERATE MEDIA CHANGE CSV FILES
# =============================================================================

cat("\n=== Generating Media Change CSV Files ===\n")

# Select top morphogens based on spatial variability and expression
if (!is.null(morphogen_spatial) && nrow(morphogen_spatial) > 0) {
  # Combine spatial score with expression level
  top_morphogens <- morphogen_spatial %>%
    left_join(morphogen_stats, by = "gene") %>%
    mutate(combined_score = spatial_score * log1p(mean_expr)) %>%
    filter(pct_expressing > 5) %>%  # Filter for morphogens expressed in >5% of cells
    arrange(desc(combined_score)) %>%
    head(6)  # Top 6 for tube rack (A1-A6)

} else {
  # Fallback: use expression stats only
  top_morphogens <- morphogen_stats %>%
    filter(pct_expressing > 5) %>%
    arrange(desc(mean_expr)) %>%
    head(6)
}

cat("Top morphogens selected for media change:\n")
print(top_morphogens)

# Create tube rack mapping
tube_positions <- c("A1", "A2", "A3", "A4", "A5", "A6")
reagent_mapping <- data.frame(
  position = paste0(tube_positions[1:nrow(top_morphogens)], "_tube"),
  reagent = tolower(gsub("-", "_", top_morphogens$gene))
)

# Determine concentration levels based on expression gradients
# Map expression to concentration levels 1-N
get_concentration_level <- function(expr_value, expr_range, n_levels) {
  if (is.na(expr_value) || expr_value == 0) return(1)
  normalized <- (expr_value - expr_range[1]) / (expr_range[2] - expr_range[1])
  level <- ceiling(normalized * n_levels)
  return(max(1, min(n_levels, level)))
}

# Generate plate layout
# This creates a gradient based on spatial position or cluster
plate_wells <- expand.grid(
  row = LETTERS[1:8],
  col = 1:12,
  stringsAsFactors = FALSE
) %>%
  mutate(well = paste0(row, col, "_plate"))

# For each well, assign concentration levels based on position
# Creating a gradient across the plate
plate_layout <- plate_wells %>%
  mutate(
    row_num = match(row, LETTERS),
    # Create gradients: rows for first morphogen, columns for second, etc.
    gradient_1 = ceiling(row_num / 2),  # Levels 1-4 for rows
    gradient_2 = ceiling(col / 3),       # Levels 1-4 for columns
    gradient_3 = ((row_num - 1) %% 4) + 1,  # Alternating pattern
    gradient_4 = ((col - 1) %% 4) + 1
  )

# Build the CSV content
csv_lines <- c("#Starting reagent locations")

for (i in 1:nrow(reagent_mapping)) {
  csv_lines <- c(csv_lines, paste(reagent_mapping$position[i], reagent_mapping$reagent[i], sep = ","))
}

csv_lines <- c(csv_lines, "#Plate layout")

# Generate plate layout lines
for (i in 1:nrow(plate_layout)) {
  well_line <- plate_layout$well[i]

  # Add each reagent with its concentration level
  for (j in 1:nrow(reagent_mapping)) {
    # Assign concentration based on gradient pattern
    if (j == 1) {
      conc <- plate_layout$gradient_1[i]
    } else if (j == 2) {
      conc <- plate_layout$gradient_2[i]
    } else if (j == 3) {
      conc <- plate_layout$gradient_3[i]
    } else if (j == 4) {
      conc <- plate_layout$gradient_4[i]
    } else {
      conc <- 1  # Default for additional morphogens
    }

    well_line <- paste(well_line, reagent_mapping$reagent[j], conc, sep = ",")
  }

  csv_lines <- c(csv_lines, well_line)
}

# Write the CSV file
output_csv <- file.path(OUTPUT_DIR, "morphogen_media_change.csv")
writeLines(csv_lines, output_csv)
cat("\nMedia change CSV written to:", output_csv, "\n")

# =============================================================================
# VISUALIZATION
# =============================================================================

cat("\n=== Generating Visualizations ===\n")

# Expression heatmap of morphogens
if (length(morphogens_present) > 0) {
  pdf(file.path(OUTPUT_DIR, "morphogen_expression_heatmap.pdf"), width = 12, height = 10)

  # Subset to top expressed morphogens
  top_expressed <- morphogen_stats %>%
    filter(pct_expressing > 1) %>%
    arrange(desc(mean_expr)) %>%
    head(30) %>%
    pull(gene)

  if (length(top_expressed) > 1) {
    DoHeatmap(seurat_obj, features = top_expressed, size = 3) +
      theme(axis.text.y = element_text(size = 8))
  }
  dev.off()

  # Feature plots for top morphogens
  pdf(file.path(OUTPUT_DIR, "morphogen_feature_plots.pdf"), width = 15, height = 12)

  plot_genes <- intersect(top_morphogens$gene, rownames(seurat_obj))
  if (length(plot_genes) > 0) {
    print(FeaturePlot(seurat_obj, features = plot_genes, ncol = 3))
  }
  dev.off()

  # Spatial plots if coordinates available
  if (has_spatial) {
    pdf(file.path(OUTPUT_DIR, "morphogen_spatial_plots.pdf"), width = 15, height = 12)

    for (gene in plot_genes) {
      p <- ggplot(data.frame(
        x = seurat_obj$spatial_x,
        y = seurat_obj$spatial_y,
        expr = as.numeric(GetAssayData(seurat_obj, slot = "data")[gene, ])
      )) +
        geom_point(aes(x = x, y = y, color = expr), size = 0.5) +
        scale_color_viridis_c() +
        labs(title = gene, color = "Expression") +
        theme_minimal() +
        coord_fixed()

      print(p)
    }
    dev.off()
  }
}

# =============================================================================
# SAVE PROCESSED OBJECT
# =============================================================================

cat("\n=== Saving Processed Object ===\n")
saveRDS(seurat_obj, file.path(OUTPUT_DIR, "cs7_processed_seurat.rds"))

cat("\n=== Analysis Complete ===\n")
cat("Output files saved to:", OUTPUT_DIR, "\n")
cat("\nGenerated files:\n")
cat("  - QC_plots.pdf\n")
cat("  - variable_features.pdf\n")
cat("  - elbow_plot.pdf\n")
cat("  - UMAP_clusters.pdf\n")
cat("  - all_spatial_correlations.csv (if spatial coords available)\n")
cat("  - spatially_variable_morphogens.csv\n")
cat("  - morphogen_expression_stats.csv\n")
cat("  - morphogen_media_change.csv <-- Use this for Opentrons!\n")
cat("  - morphogen_expression_heatmap.pdf\n")
cat("  - morphogen_feature_plots.pdf\n")
cat("  - morphogen_spatial_plots.pdf (if spatial coords available)\n")
cat("  - cs7_processed_seurat.rds\n")
