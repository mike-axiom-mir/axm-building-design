import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load(ROOT / "tools" / "build_service_pavilion.py", "building_base")
geo = load(ROOT / "tools" / "build_service_pavilion_topology_candidate.py", "building_geometry_candidate")


class ServicePavilionTopologyCandidateTests(unittest.TestCase):
    def test_historical_face_table_is_exact_donor_state(self):
        self.assertEqual(tuple(tuple(face) for face in base.FACES), geo.HISTORICAL_FACES)
        self.assertEqual(
            geo.local_edge_metrics(geo.HISTORICAL_FACES),
            {
                "edge_count": 20,
                "boundary_edge_count": 6,
                "nonmanifold_edge_count": 2,
                "orientation_conflict_edge_count": 4,
            },
        )

    def test_candidate_face_table_is_closed_and_consistently_oriented(self):
        self.assertEqual(
            geo.local_edge_metrics(geo.CANDIDATE_FACES),
            {
                "edge_count": 18,
                "boundary_edge_count": 0,
                "nonmanifold_edge_count": 0,
                "orientation_conflict_edge_count": 0,
            },
        )

    def test_candidate_is_outward_on_source_box_vertex_order(self):
        vertices = base.box_vertices([0.0, 0.0, 0.0], [2.0, 3.0, 4.0])
        self.assertEqual(
            geo.outward_counts(vertices, geo.CANDIDATE_FACES),
            {"outward": 12, "inward": 0, "tangent": 0},
        )
        self.assertEqual(
            geo.outward_counts(vertices, geo.HISTORICAL_FACES),
            {"outward": 6, "inward": 6, "tangent": 0},
        )


if __name__ == "__main__":
    unittest.main()
