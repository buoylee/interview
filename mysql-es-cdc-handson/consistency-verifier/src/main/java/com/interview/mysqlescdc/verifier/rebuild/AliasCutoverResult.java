package com.interview.mysqlescdc.verifier.rebuild;
public record AliasCutoverResult(String oldIndex,String newIndex,boolean alreadyApplied) {}
