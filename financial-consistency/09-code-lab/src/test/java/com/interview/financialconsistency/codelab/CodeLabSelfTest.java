package com.interview.financialconsistency.codelab;

import com.interview.financialconsistency.codelab.runner.CodeLabRunner;

public final class CodeLabSelfTest {
    private CodeLabSelfTest() {
    }

    public static void main(String[] args) {
        CodeLabRunner.main(new String[0]);
        System.out.println("SELF_TEST_PASS");
    }
}
