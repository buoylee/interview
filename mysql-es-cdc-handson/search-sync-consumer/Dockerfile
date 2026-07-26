FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/search-sync-consumer-0.1.0-SNAPSHOT.jar app.jar
USER 10001
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
