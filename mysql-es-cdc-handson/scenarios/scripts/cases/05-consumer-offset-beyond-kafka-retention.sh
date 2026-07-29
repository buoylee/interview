scenario_mutate(){ m6_execute_case consumer-offset-beyond-kafka-retention mutate; }
scenario_assert_intermediate(){ m6_execute_case consumer-offset-beyond-kafka-retention intermediate; }
scenario_recover(){ m6_execute_case consumer-offset-beyond-kafka-retention recover; }
