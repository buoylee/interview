package com.interview.mysqlescdc.verifier;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Path;
import java.util.Set;
import java.util.TreeSet;

import javax.xml.parsers.DocumentBuilderFactory;

import org.junit.jupiter.api.Test;
import org.w3c.dom.Element;

class ArchitectureBoundaryTest {
    @Test
    void authored_generated_and_compiled_code_obey_module_boundary() throws Exception {
        ProcessBuilder builder = new ProcessBuilder(
                "bash", "../tests/contracts/check-verifier-independence.sh", ".")
                .redirectErrorStream(true);
        builder.environment().put("VERIFIER_TEST_CLASSPATH", System.getProperty("java.class.path"));
        Process process = builder.start();
        process.getOutputStream().close();
        process.waitFor();
        String checkerOutput = new String(process.getInputStream().readAllBytes());
        assertThat(process.exitValue())
                .as(checkerOutput)
                .isZero();
    }

    @Test
    void pom_has_only_the_locked_dependencies() throws Exception {
        var document = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(Path.of("pom.xml").toFile());
        var dependencies = document.getElementsByTagName("dependency");
        Set<String> artifactIds = new TreeSet<>();
        for (int index = 0; index < dependencies.getLength(); index++) {
            Element dependency = (Element) dependencies.item(index);
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
}
