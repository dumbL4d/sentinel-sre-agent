"""Tests for demo scenarios."""

from sentinel.scenarios import SCENARIOS, get_scenario, list_scenarios


class TestScenarios:
    def test_scenarios_exist(self):
        assert len(SCENARIOS) >= 4

    def test_get_scenario(self):
        scenario = get_scenario("scenario-001")
        assert scenario is not None
        assert scenario.title == "Latency Spike Investigation"

    def test_list_scenarios(self):
        scenarios = list_scenarios()
        assert len(scenarios) >= 4
        assert all("id" in s for s in scenarios)

    def test_scenario_has_required_fields(self):
        for s in SCENARIOS:
            assert s.id
            assert s.title
            assert s.mission
            assert s.expected_tools
            assert s.expected_findings
