shell.options.useWizards = false;
const user = os.getenv('MYSQL_CLUSTER_ADMIN') || 'icadmin';
const password = os.getenv('MYSQL_CLUSTER_ADMIN_PASSWORD') || 'ha-cluster';
const seed = os.getenv('MYSQL_SEED') || 'db1';
const dryRun = (os.getenv('MYSQL_REBOOT_DRY_RUN') || '1') === '1';

shell.connect({scheme: 'mysql', user, password, host: seed, port: 3306});
const cluster = dba.rebootClusterFromCompleteOutage('haLabCluster', {dryRun});
if (dryRun) {
  print(JSON.stringify({dryRun: true, cluster: 'haLabCluster', seed, ok: true}));
} else {
  print(JSON.stringify(cluster.status({extended: 2}), null, 2));
}
