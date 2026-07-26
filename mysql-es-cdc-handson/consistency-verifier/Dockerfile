FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/consistency-verifier-0.1.0-SNAPSHOT.jar app.jar
USER 10001
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
