scenario_mutate(){ m6_execute_case consumer-crash-after-elasticsearch-before-offset mutate; }
scenario_assert_intermediate(){ m6_execute_case consumer-crash-after-elasticsearch-before-offset intermediate; }
scenario_recover(){ m6_execute_case consumer-crash-after-elasticsearch-before-offset recover; }
