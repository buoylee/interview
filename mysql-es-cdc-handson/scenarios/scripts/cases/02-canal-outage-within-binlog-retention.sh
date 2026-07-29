scenario_mutate(){ m6_execute_case canal-outage-within-binlog-retention mutate; }
scenario_assert_intermediate(){ m6_execute_case canal-outage-within-binlog-retention intermediate; }
scenario_recover(){ m6_execute_case canal-outage-within-binlog-retention recover; }
