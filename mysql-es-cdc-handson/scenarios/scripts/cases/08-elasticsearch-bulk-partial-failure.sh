scenario_mutate(){ m6_execute_case elasticsearch-bulk-partial-failure mutate; }
scenario_assert_intermediate(){ m6_execute_case elasticsearch-bulk-partial-failure intermediate; }
scenario_recover(){ m6_execute_case elasticsearch-bulk-partial-failure recover; }
