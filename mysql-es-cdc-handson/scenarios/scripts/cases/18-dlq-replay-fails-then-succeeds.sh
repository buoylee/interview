scenario_mutate(){ m6_execute_case dlq-replay-fails-then-succeeds mutate; }
scenario_assert_intermediate(){ m6_execute_case dlq-replay-fails-then-succeeds intermediate; }
scenario_recover(){ m6_execute_case dlq-replay-fails-then-succeeds recover; }
