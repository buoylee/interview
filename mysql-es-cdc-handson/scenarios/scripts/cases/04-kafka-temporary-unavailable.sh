scenario_mutate(){ m6_execute_case kafka-temporary-unavailable mutate; }
scenario_assert_intermediate(){ m6_execute_case kafka-temporary-unavailable intermediate; }
scenario_recover(){ m6_execute_case kafka-temporary-unavailable recover; }
