shell.options.useWizards = false;

const rootPassword = os.getenv('MYSQL_ROOT_PASSWORD') || 'ha-root';
const adminUser = os.getenv('MYSQL_CLUSTER_ADMIN') || 'icadmin';
const adminPassword = os.getenv('MYSQL_CLUSTER_ADMIN_PASSWORD') || 'ha-cluster';
const clusterName = 'haLabCluster';
const members = [
  {host: 'db1', weight: 100},
  {host: 'db2', weight: 80},
  {host: 'db3', weight: 60},
];

function connection(user, password, host) {
  return {scheme: 'mysql', user, password, host, port: 3306};
}

for (const member of members) {
  try {
    dba.configureInstance(connection('root', rootPassword, member.host), {
      clusterAdmin: adminUser,
      clusterAdminPassword: adminPassword,
    });
  } catch (error) {
    const alreadyInCluster =
      error.message.includes('belongs to an InnoDB Cluster') ||
      error.message.includes('clusterAdmin option is not allowed');
    if (!alreadyInCluster) {
      throw error;
    }
  }
}

shell.connect(connection(adminUser, adminPassword, 'db1'));
let cluster;
try {
  cluster = dba.getCluster(clusterName);
} catch (error) {
  cluster = dba.createCluster(clusterName, {
    communicationStack: 'MYSQL',
    consistency: 'BEFORE_ON_PRIMARY_FAILOVER',
    exitStateAction: 'OFFLINE_MODE',
    autoRejoinTries: 3,
    expelTimeout: 5,
    memberWeight: 100,
  });
}

for (const member of members.slice(1)) {
  const address = `${member.host}:3306`;
  const topology = cluster.status().defaultReplicaSet.topology;
  if (!Object.prototype.hasOwnProperty.call(topology, address)) {
    cluster.addInstance(connection(adminUser, adminPassword, member.host), {
      recoveryMethod: 'clone',
      memberWeight: member.weight,
    });
  }
}

print(JSON.stringify(cluster.status({extended: 1}), null, 2));
