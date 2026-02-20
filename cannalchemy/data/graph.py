"""Build NetworkX knowledge graph from SQLite data."""
import sqlite3
import networkx as nx


def build_knowledge_graph(conn: sqlite3.Connection) -> nx.DiGraph:
    """Build the molecular interaction knowledge graph.

    Node types: molecule, receptor, effect, strain
    Edge types: binds_to, contains, produces, reports

    Node IDs are prefixed: 'molecule:myrcene', 'receptor:CB1', etc.
    """
    G = nx.DiGraph()

    # Add molecule nodes
    for row in conn.execute("SELECT id, name, molecule_type, smiles, molecular_weight FROM molecules").fetchall():
        G.add_node(
            f"molecule:{row[1]}",
            node_type="molecule",
            db_id=row[0],
            name=row[1],
            molecule_type=row[2],
            smiles=row[3] or "",
            molecular_weight=row[4],
        )

    # Add receptor nodes
    for row in conn.execute("SELECT id, name, gene_name, location, function FROM receptors").fetchall():
        G.add_node(
            f"receptor:{row[1]}",
            node_type="receptor",
            db_id=row[0],
            name=row[1],
            gene_name=row[2],
            location=row[3] or "",
            function=row[4] or "",
        )

    # Add effect nodes
    for row in conn.execute("SELECT id, name, category FROM effects").fetchall():
        G.add_node(
            f"effect:{row[1]}",
            node_type="effect",
            db_id=row[0],
            name=row[1],
            category=row[2],
        )

    # Add strain nodes (only strains with compositions)
    for row in conn.execute(
        "SELECT DISTINCT s.id, s.name, s.strain_type FROM strains s "
        "JOIN strain_compositions sc ON s.id = sc.strain_id"
    ).fetchall():
        G.add_node(
            f"strain:{row[1]}",
            node_type="strain",
            db_id=row[0],
            name=row[1],
            strain_type=row[2],
        )

    # Add binding edges (molecule -> receptor)
    for row in conn.execute(
        "SELECT m.name, r.name, ba.ki_nm, ba.ic50_nm, ba.ec50_nm, ba.action_type, ba.source "
        "FROM binding_affinities ba "
        "JOIN molecules m ON ba.molecule_id = m.id "
        "JOIN receptors r ON ba.receptor_id = r.id"
    ).fetchall():
        # Convert Ki to a 0-1 affinity score (lower Ki = stronger binding)
        ki = row[2]
        affinity_score = 1.0 / (1.0 + (ki / 100.0)) if ki else 0.5
        G.add_edge(
            f"molecule:{row[0]}",
            f"receptor:{row[1]}",
            edge_type="binds_to",
            ki_nm=row[2],
            ic50_nm=row[3],
            ec50_nm=row[4],
            action_type=row[5] or "",
            affinity_score=affinity_score,
            source=row[6] or "",
        )

    # Add composition edges (strain -> molecule)
    for row in conn.execute(
        "SELECT s.name, m.name, sc.percentage, sc.measurement_type "
        "FROM strain_compositions sc "
        "JOIN strains s ON sc.strain_id = s.id "
        "JOIN molecules m ON sc.molecule_id = m.id"
    ).fetchall():
        strain_node = f"strain:{row[0]}"
        mol_node = f"molecule:{row[1]}"
        if G.has_node(strain_node) and G.has_node(mol_node):
            G.add_edge(
                strain_node, mol_node,
                edge_type="contains",
                percentage=row[2],
                measurement_type=row[3] or "",
            )

    # Add effect report edges (strain -> effect)
    for row in conn.execute(
        "SELECT s.name, e.name, er.report_count, er.source "
        "FROM effect_reports er "
        "JOIN strains s ON er.strain_id = s.id "
        "JOIN effects e ON er.effect_id = e.id"
    ).fetchall():
        strain_node = f"strain:{row[0]}"
        effect_node = f"effect:{row[1]}"
        if G.has_node(strain_node) and G.has_node(effect_node):
            G.add_edge(
                strain_node, effect_node,
                edge_type="reports",
                report_count=row[2],
                source=row[3] or "",
            )

    return G


def get_molecule_pathways(G: nx.DiGraph, molecule_name: str) -> list[dict]:
    """Get all pathways from a molecule to effects through receptors.

    Returns list of pathway dicts:
    {molecule, receptor, affinity, action_type, connected_effects}
    """
    mol_node = f"molecule:{molecule_name}"
    if not G.has_node(mol_node):
        return []

    pathways = []
    for _, receptor_node, binding_data in G.edges(mol_node, data=True):
        if binding_data.get("edge_type") != "binds_to":
            continue

        pathway = {
            "molecule": molecule_name,
            "receptor": G.nodes[receptor_node]["name"],
            "ki_nm": binding_data.get("ki_nm"),
            "affinity_score": binding_data.get("affinity_score"),
            "action_type": binding_data.get("action_type"),
            "receptor_function": G.nodes[receptor_node].get("function", ""),
        }
        pathways.append(pathway)

    return pathways


def get_strain_profile(G: nx.DiGraph, strain_name: str) -> dict:
    """Get complete profile for a strain: compositions, effects, pathways."""
    strain_node = f"strain:{strain_name}"
    if not G.has_node(strain_node):
        return {}

    profile = {
        "name": strain_name,
        "type": G.nodes[strain_node].get("strain_type"),
        "compositions": [],
        "effects": [],
        "pathways": [],
    }

    for _, target, data in G.edges(strain_node, data=True):
        if data.get("edge_type") == "contains":
            mol_name = G.nodes[target]["name"]
            profile["compositions"].append({
                "molecule": mol_name,
                "percentage": data["percentage"],
                "type": G.nodes[target].get("molecule_type"),
            })
            # Get pathways for this molecule
            mol_pathways = get_molecule_pathways(G, mol_name)
            profile["pathways"].extend(mol_pathways)

        elif data.get("edge_type") == "reports":
            profile["effects"].append({
                "effect": G.nodes[target]["name"],
                "report_count": data.get("report_count", 0),
                "category": G.nodes[target].get("category"),
            })

    # Sort by percentage/count
    profile["compositions"].sort(key=lambda x: x["percentage"], reverse=True)
    profile["effects"].sort(key=lambda x: x["report_count"], reverse=True)

    return profile
