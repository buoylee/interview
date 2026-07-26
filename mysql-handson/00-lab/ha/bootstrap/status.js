shell.options.useWizards = false;
const user = os.getenv('MYSQL_CLUSTER_ADMIN') || 'icadmin';
const password = os.getenv('MYSQL_CLUSTER_ADMIN_PASSWORD') || 'ha-cluster';
shell.connect({scheme: 'mysql', user, password, host: os.getenv('MYSQL_SEED') || 'db1', port: 3306});
print(JSON.stringify(dba.getCluster('haLabCluster').status({extended: 2}), null, 2));
