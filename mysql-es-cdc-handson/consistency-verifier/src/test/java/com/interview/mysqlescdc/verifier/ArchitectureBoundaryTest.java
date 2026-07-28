package com.interview.mysqlescdc.verifier;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Stream;

import javax.xml.parsers.DocumentBuilderFactory;

import org.junit.jupiter.api.Test;
import org.w3c.dom.Element;

class ArchitectureBoundaryTest {
    private static final String FORBIDDEN_PACKAGE = String.join(".",
            "com", "interview", "mysqlescdc", "consumer");
    private static final String FORBIDDEN_ARTIFACT = String.join("-", "search", "sync", "consumer");

    @Test
    void verifier_sources_do_not_reference_consumer_implementation() throws IOException {
        for (Path root : List.of(Path.of("src/main/java"), Path.of("src/test/java"))) {
            try (Stream<Path> files = Files.walk(root)) {
                assertThat(files.filter(path -> path.toString().endsWith(".java")))
                        .allSatisfy(path -> assertThat(Files.readString(path))
                                .doesNotContain(FORBIDDEN_PACKAGE)
                                .doesNotContain(FORBIDDEN_ARTIFACT));
            }
        }
    }

    @Test
    void verifier_pom_and_resolved_test_classpath_exclude_consumer_module() throws Exception {
        var document = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(Path.of("pom.xml").toFile());
        var dependencies = document.getElementsByTagName("dependency");
        Set<String> artifactIds = new TreeSet<>();
        for (int index = 0; index < dependencies.getLength(); index++) {
            Element dependency = (Element) dependencies.item(index);
            assertThat(dependency.getTextContent()).doesNotContain(FORBIDDEN_ARTIFACT);
            artifactIds.add(dependency.getElementsByTagName("artifactId").item(0).getTextContent());
        }
        assertThat(artifactIds).containsExactly(
                "mysql-connector-j",
                "spring-boot-starter-actuator",
                "spring-boot-starter-jdbc",
                "spring-boot-starter-test",
                "spring-boot-starter-webmvc",
                "spring-kafka");

        Element mysql = findDependency(dependencies, "mysql-connector-j");
        assertThat(mysql.getElementsByTagName("scope").item(0).getTextContent()).isEqualTo("runtime");

        assertThat(System.getProperty("java.class.path")).doesNotContain(FORBIDDEN_ARTIFACT);
    }

    private Element findDependency(org.w3c.dom.NodeList dependencies, String artifactId) {
        for (int index = 0; index < dependencies.getLength(); index++) {
            Element dependency = (Element) dependencies.item(index);
            if (artifactId.equals(dependency.getElementsByTagName("artifactId").item(0).getTextContent())) {
                return dependency;
            }
        }
        throw new AssertionError("missing dependency: " + artifactId);
    }

    @Test
    void compiled_verifier_classes_do_not_reference_consumer_bytecode() throws IOException {
        Path classes = Path.of("target/classes");
        if (!Files.exists(classes)) {
            return;
        }
        try (Stream<Path> files = Files.walk(classes)) {
            assertThat(files.filter(path -> path.toString().endsWith(".class")))
                    .allSatisfy(path -> {
                        try {
                            String constantPool = new String(Files.readAllBytes(path), StandardCharsets.ISO_8859_1);
                            assertThat(constantPool)
                                    .doesNotContain(FORBIDDEN_PACKAGE)
                                    .doesNotContain(FORBIDDEN_PACKAGE.replace('.', '/'));
                        } catch (IOException error) {
                            throw new AssertionError(error);
                        }
                    });
        }
    }
}
