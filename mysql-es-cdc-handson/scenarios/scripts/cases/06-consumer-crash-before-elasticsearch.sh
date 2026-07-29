scenario_mutate(){ m6_execute_case consumer-crash-before-elasticsearch mutate; }
scenario_assert_intermediate(){ m6_execute_case consumer-crash-before-elasticsearch intermediate; }
scenario_recover(){ m6_execute_case consumer-crash-before-elasticsearch recover; }
