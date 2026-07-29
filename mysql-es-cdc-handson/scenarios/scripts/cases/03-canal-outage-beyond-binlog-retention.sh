scenario_mutate(){ m6_execute_case canal-outage-beyond-binlog-retention mutate; }
scenario_assert_intermediate(){ m6_execute_case canal-outage-beyond-binlog-retention intermediate; }
scenario_recover(){ m6_execute_case canal-outage-beyond-binlog-retention recover; }
