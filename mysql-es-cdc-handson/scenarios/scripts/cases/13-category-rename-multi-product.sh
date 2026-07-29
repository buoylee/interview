scenario_mutate(){ m6_execute_case category-rename-multi-product mutate; }
scenario_assert_intermediate(){ m6_execute_case category-rename-multi-product intermediate; }
scenario_recover(){ m6_execute_case category-rename-multi-product recover; }
