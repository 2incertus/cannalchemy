"""Import Cannlytics lab data into the lab_results table."""
import sqlite3
import pandas as pd
from cannalchemy.data.cannlytics_extract import extract_measurements
from cannalchemy.data.cannlytics_config import STATE_CONFIGS


def import_state_data(
    conn: sqlite3.Connection,
    file_path: str,
    state: str,
    format_type: str,
    strain_field: str,
    chunk_size: int = 5000,
) -> dict:
    """Import a state's Cannlytics data into lab_results.

    Reads CSV in chunks for memory efficiency. Returns stats dict.
    """
    stats = {
        "rows_processed": 0,
        "rows_skipped": 0,
        "measurements_inserted": 0,
        "state": state,
    }

    if file_path.endswith(".csv"):
        chunks = pd.read_csv(file_path, chunksize=chunk_size, low_memory=False)
    else:
        chunks = [pd.read_excel(file_path)]

    for chunk in chunks:
        for _, row in chunk.iterrows():
            stats["rows_processed"] += 1

            # Get strain/product name
            strain_name = row.get(strain_field, "")
            if pd.isna(strain_name) or not str(strain_name).strip():
                strain_name = row.get("product_name", "")
            if pd.isna(strain_name) or not str(strain_name).strip():
                stats["rows_skipped"] += 1
                continue

            strain_name = str(strain_name).strip()

            # Get test date
            date_tested = ""
            for date_col in ["date_tested", "date", "date_collected"]:
                val = row.get(date_col, "")
                if pd.notna(val) and str(val).strip():
                    date_tested = str(val).strip()[:10]
                    break

            # Get lab name
            lab_name = str(row.get("lab", row.get("lims", ""))).strip()
            if pd.isna(lab_name) or lab_name == "nan":
                lab_name = ""

            # Extract measurements
            measurements = extract_measurements(row, format_type)

            if not measurements:
                stats["rows_skipped"] += 1
                continue

            # Insert into lab_results
            for m in measurements:
                conn.execute(
                    "INSERT INTO lab_results "
                    "(strain_name, normalized_strain_name, lab_name, state, "
                    "test_date, molecule_name, concentration, unit, source_file) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        strain_name,
                        "",  # Will be normalized in Task 5
                        lab_name,
                        state.upper(),
                        date_tested,
                        m["molecule"],
                        m["concentration"],
                        m["unit"],
                        file_path,
                    ),
                )
                stats["measurements_inserted"] += 1

        conn.commit()

    return stats


def import_all_states(conn: sqlite3.Connection, file_paths: dict[str, str]) -> dict:
    """Import all downloaded states. Returns combined stats."""
    all_stats = {}
    for state, path in file_paths.items():
        cfg = STATE_CONFIGS[state]
        print(f"  Importing {state.upper()} ({cfg['format']})...")
        stats = import_state_data(
            conn, path, state,
            format_type=cfg["format"],
            strain_field=cfg["strain_field"],
        )
        all_stats[state] = stats
        print(f"    Processed: {stats['rows_processed']}, "
              f"Inserted: {stats['measurements_inserted']}, "
              f"Skipped: {stats['rows_skipped']}")
    return all_stats
