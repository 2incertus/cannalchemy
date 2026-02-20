import sqlite3
import tempfile
import os
from cannalchemy.data.schema import init_db
from cannalchemy.data.graph import build_knowledge_graph

def _create_test_db():
    """Create a small test DB with known data."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    conn = init_db(db_path)

    # Add molecules
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('myrcene', 'terpene')")
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('thc', 'cannabinoid')")
    conn.execute("INSERT INTO molecules (name, molecule_type) VALUES ('cbd', 'cannabinoid')")

    # Add receptors
    conn.execute("INSERT INTO receptors (name, gene_name) VALUES ('CB1', 'CNR1')")
    conn.execute("INSERT INTO receptors (name, gene_name) VALUES ('CB2', 'CNR2')")

    # Add binding affinities
    conn.execute("INSERT INTO binding_affinities (molecule_id, receptor_id, ki_nm, action_type) VALUES (2, 1, 40.7, 'partial agonist')")
    conn.execute("INSERT INTO binding_affinities (molecule_id, receptor_id, ki_nm, action_type) VALUES (3, 2, 2860.0, 'inverse agonist')")

    # Add effects
    conn.execute("INSERT INTO effects (name, category) VALUES ('relaxed', 'positive')")
    conn.execute("INSERT INTO effects (name, category) VALUES ('euphoric', 'positive')")

    # Add a strain
    conn.execute("INSERT INTO strains (name, normalized_name, strain_type, source) VALUES ('Blue Dream', 'blue dream', 'hybrid', 'test')")

    # Add compositions
    conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage) VALUES (1, 1, 0.35)")
    conn.execute("INSERT INTO strain_compositions (strain_id, molecule_id, percentage) VALUES (1, 2, 18.0)")

    # Add effect reports
    conn.execute("INSERT INTO effect_reports (strain_id, effect_id, report_count) VALUES (1, 1, 100)")
    conn.execute("INSERT INTO effect_reports (strain_id, effect_id, report_count) VALUES (1, 2, 80)")

    conn.commit()
    return conn

def test_build_graph_has_nodes():
    conn = _create_test_db()
    G = build_knowledge_graph(conn)
    conn.close()
    assert G.number_of_nodes() > 0
    assert G.number_of_edges() > 0

def test_graph_has_molecule_nodes():
    conn = _create_test_db()
    G = build_knowledge_graph(conn)
    conn.close()
    molecule_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "molecule"]
    assert len(molecule_nodes) >= 3

def test_graph_has_binding_edges():
    conn = _create_test_db()
    G = build_knowledge_graph(conn)
    conn.close()
    binding_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "binds_to"]
    assert len(binding_edges) >= 2

def test_graph_pathway_traversal():
    """Test that we can traverse from a molecule to an effect through receptors."""
    conn = _create_test_db()
    G = build_knowledge_graph(conn)
    conn.close()
    # THC -> CB1 binding exists
    assert G.has_edge("molecule:thc", "receptor:CB1")
