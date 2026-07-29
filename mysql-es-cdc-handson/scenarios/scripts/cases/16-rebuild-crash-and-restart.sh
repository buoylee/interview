scenario_mutate(){ m6_execute_case rebuild-crash-and-restart mutate; }
scenario_assert_intermediate(){ m6_execute_case rebuild-crash-and-restart intermediate; }
scenario_recover(){ m6_execute_case rebuild-crash-and-restart recover; }
