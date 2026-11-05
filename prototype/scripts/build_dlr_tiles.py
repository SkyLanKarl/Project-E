import argparse
import sqlite3
from pathlib import Path

import mapbox_vector_tile
import mercantile
from pyproj import Transformer
from shapely import wkb

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/coastline/dlr-tandemx-10m/TanDEM-X_hires_coastline_global_2010-2015_V1.gpkg"
OUTPUT = ROOT / "prototype/tiles/coastline"
WORLD_METRES = 40075016.68557849


def geometry_from_gpkg(blob):
    flags = blob[3]
    envelope_code = (flags >> 1) & 0x07
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    offset = 8 + envelope_sizes[envelope_code]
    return wkb.loads(blob[offset:])


def build_tile(connection, tile, to_wgs84, to_world):
    geographic_bounds = mercantile.bounds(tile)
    projected_bounds = to_world.transform_bounds(*geographic_bounds)
    rows = connection.execute("""
        SELECT p.geom FROM "Polygon" p
        JOIN rtree_Polygon_geom r ON p.fid = r.id
        WHERE r.maxx >= ? AND r.minx <= ? AND r.maxy >= ? AND r.miny <= ?
    """, (
        projected_bounds[0], projected_bounds[2],
        projected_bounds[1], projected_bounds[3],
    )).fetchall()
    tolerance = WORLD_METRES / (256 * (2 ** tile.z)) * 0.35
    from shapely.geometry import box
    tile_box = box(*geographic_bounds)
    features = []
    for (blob,) in rows:
        geometry = geometry_from_gpkg(blob)
        if tolerance > 0:
            geometry = geometry.simplify(tolerance, preserve_topology=True)
        if geometry.is_empty:
            continue
        geometry = wkb.loads(wkb.dumps(geometry))
        from shapely.ops import transform
        geometry = transform(to_wgs84.transform, geometry)
        if not geometry.is_valid:
            from shapely import make_valid
            geometry = make_valid(geometry)
        geometry = geometry.intersection(tile_box)
        if geometry.is_empty:
            continue
        features.append({"type": "Feature", "geometry": geometry, "properties": {}})
    payload = mapbox_vector_tile.encode([{
        "name": "land",
        "features": features,
    }], default_options={
        "y_coord_down": False,
        "quantize_bounds": tuple(geographic_bounds),
    })
    output = OUTPUT / str(tile.z) / str(tile.x) / f"{tile.y}.pbf"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    return len(features)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-zoom", type=int, default=0)
    parser.add_argument("--max-zoom", type=int, default=6)
    parser.add_argument("--tile")
    args = parser.parse_args()
    to_wgs84 = Transformer.from_crs(3395, 4326, always_xy=True)
    to_world = Transformer.from_crs(4326, 3395, always_xy=True)
    connection = sqlite3.connect(f"file:{SOURCE}?mode=ro", uri=True)
    if args.tile:
        z, x, y = (int(value) for value in args.tile.split("/"))
        tiles = [mercantile.Tile(x=x, y=y, z=z)]
    else:
        tiles = (
            tile for z in range(args.min_zoom, args.max_zoom + 1)
            for tile in [mercantile.Tile(x=x, y=y, z=z) for x in range(2 ** z) for y in range(2 ** z)]
        )
    total = 0
    for index, tile in enumerate(tiles, 1):
        output = OUTPUT / str(tile.z) / str(tile.x) / f"{tile.y}.pbf"
        if output.exists():
            continue
        total += build_tile(connection, tile, to_wgs84, to_world)
        if index % 100 == 0:
            print(f"Processed {index} tiles; current {tile.z}/{tile.x}/{tile.y}", flush=True)
    connection.close()
    print(f"Completed. Wrote or retained features in tiles: {total}")


if __name__ == "__main__":
    main()
