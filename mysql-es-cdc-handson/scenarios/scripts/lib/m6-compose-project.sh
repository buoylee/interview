#!/usr/bin/env bash

m6_compose_project() {
  case "${1:-}" in
    mysql-es-cdc-handson-m6-task4|mysql-es-cdc-handson-m6-task6) printf '%s\n' "$1" ;;
    *) return 64 ;;
  esac
}

m6_compose_marker_name() {
  case "${1:-}" in
    mysql-es-cdc-handson-m6-task4) printf '.m6-task4-project.json\n' ;;
    mysql-es-cdc-handson-m6-task6) printf '.m6-task6-project.json\n' ;;
    *) return 64 ;;
  esac
}
