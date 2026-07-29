scenario_mutate(){ m6_execute_case manual-elasticsearch-drift mutate; }
scenario_assert_intermediate(){ m6_execute_case manual-elasticsearch-drift intermediate; }
scenario_recover(){ m6_execute_case manual-elasticsearch-drift recover; }
