scenario_mutate(){ m6_execute_case delete-then-old-event-replay mutate; }
scenario_assert_intermediate(){ m6_execute_case delete-then-old-event-replay intermediate; }
scenario_recover(){ m6_execute_case delete-then-old-event-replay recover; }
