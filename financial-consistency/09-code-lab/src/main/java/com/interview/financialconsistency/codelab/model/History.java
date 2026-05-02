package com.interview.financialconsistency.codelab.model;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Objects;
import java.util.Set;

public record History(List<HistoryItem> items) {
    public History {
        Objects.requireNonNull(items);
        items = List.copyOf(items);
    }

    public static History of(HistoryItem... items) {
        Objects.requireNonNull(items);
        return new History(List.copyOf(Arrays.asList(items)));
    }

    public List<Fact> facts() {
        List<Fact> facts = new ArrayList<>();
        for (HistoryItem item : items) {
            if (item instanceof Fact fact) {
                facts.add(fact);
            }
        }
        return List.copyOf(facts);
    }

    public List<Fact> facts(FactType type) {
        List<Fact> facts = new ArrayList<>();
        for (Fact fact : facts()) {
            if (fact.type() == type) {
                facts.add(fact);
            }
        }
        return List.copyOf(facts);
    }

    public List<Fact> factsByBusinessKey(String businessKey) {
        List<Fact> facts = new ArrayList<>();
        for (Fact fact : facts()) {
            if (fact.businessKey().equals(businessKey)) {
                facts.add(fact);
            }
        }
        return List.copyOf(facts);
    }

    public History reduceTo(Set<String> ids) {
        List<HistoryItem> reducedItems = new ArrayList<>();
        for (HistoryItem item : items) {
            if (ids.contains(item.id())) {
                reducedItems.add(item);
            }
        }
        return new History(reducedItems);
    }
}
