# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Create a visual gallery preview showing all static charts
"""

from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt


def create_gallery():
    """Create a gallery preview of all static charts"""

    viz_dir = Path(__file__).parent / "performance_visualizations"

    # Get all PNG files
    png_files = sorted(viz_dir.glob("*.png"))

    if not png_files:
        print("No PNG files found!")
        return

    # Create grid layout
    n_images = len(png_files)
    cols = 3
    rows = (n_images + cols - 1) // cols

    fig = plt.figure(figsize=(20, rows * 6), facecolor="#1a1a1a")

    for idx, png_file in enumerate(png_files):
        ax = plt.subplot(rows, cols, idx + 1)

        try:
            img = mpimg.imread(str(png_file))
            ax.imshow(img)
            ax.axis("off")

            # Add title
            title = png_file.stem.replace("_", " ").title()
            ax.set_title(title, fontsize=14, fontweight="bold", color="white", pad=10)

        except Exception:
            ax.text(
                0.5,
                0.5,
                f"Error loading\n{png_file.name}",
                ha="center",
                va="center",
                fontsize=12,
                color="white",
            )
            ax.axis("off")

    plt.suptitle(
        "🎨 Performance Visualization Gallery",
        fontsize=24,
        fontweight="bold",
        color="white",
        y=0.995,
    )

    plt.tight_layout()

    output_file = viz_dir / "gallery_preview.png"
    plt.savefig(
        output_file, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor()
    )
    plt.close()

    print(f"✓ Created gallery preview: {output_file}")
    print(f"  → Shows all {n_images} visualizations in one image")
    print("  → Perfect for quick overview")


if __name__ == "__main__":
    print("\n🎨 Creating Gallery Preview...\n")
    create_gallery()
    print("\n✅ Gallery preview complete!")
