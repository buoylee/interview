package com.interview.financialconsistency.codelab.generator;

import com.interview.financialconsistency.codelab.model.History;

public record ExperimentCase(String name, String scenario, History history, boolean expectedToPass) {
}
