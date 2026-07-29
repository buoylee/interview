scenario_mutate(){ m6_execute_case rebuild-with-concurrent-writes mutate; }
scenario_assert_intermediate(){ m6_execute_case rebuild-with-concurrent-writes intermediate; }
scenario_recover(){ m6_execute_case rebuild-with-concurrent-writes recover; }
