from charmhelpers.core import hookenv
from charms.layer.kafka import Kafka
from charms.reactive import set_state, remove_state, when, when_not
from charms.reactive.helpers import any_file_changed
from jujubigdata.utils import DistConfig


@when_not('kafka.installed')
def install_kafka(*args):
    kafka = Kafka()
    if kafka.verify_resources():
        hookenv.status_set('maintenance', 'Installing Kafka')
        kafka.install()
        kafka.open_ports()
        set_state('kafka.installed')


@when('kafka.installed')
@when_not('zookeeper.joined')
def waiting_for_zookeeper_relation():
    hookenv.status_set('blocked', 'Waiting for relation to Zookeeper')


@when('kafka.installed', 'zookeeper.joined')
@when_not('kafka.started', 'zookeeper.ready')
def waiting_for_zookeeper_ready(zk):
    hookenv.status_set('waiting', 'Waiting for Zookeeper to become ready')


@when('kafka.installed', 'zookeeper.ready')
@when_not('kafka.started')
def configure_kafka(zk):
    hookenv.status_set('maintenance', 'Setting up Kafka')
    kafka = Kafka()
    zks = zk.zookeepers()
    kafka.configure_kafka(zks)
    kafka.start()
    set_state('kafka.started')
    hookenv.status_set('active', 'Ready')


@when('kafka.started', 'zookeeper.ready')
def configure_kafka_zookeepers(zk):
    """Configure ready zookeepers and restart kafka if needed.

    As zks come and go, server.properties will be updated. When that file
    changes, restart Kafka and set appropriate status messages.
    """
    hookenv.log('Checking Zookeeper configuration')
    kafka = Kafka()
    zks = zk.zookeepers()
    kafka.configure_kafka(zks)

    server_cfg = DistConfig().path('kafka_conf') / 'server.properties'
    if any_file_changed([server_cfg]):
        hookenv.status_set('maintenance', 'Server config changed: restarting Kafka')
        hookenv.log('Server config changed: restarting Kafka')
        kafka.restart()
        hookenv.status_set('active', 'Ready')


@when('kafka.started')
@when_not('zookeeper.ready')
def stop_kafka_waiting_for_zookeeper_ready():
    hookenv.status_set('maintenance', 'Zookeeper not ready, stopping Kafka')
    kafka = Kafka()
    kafka.stop()
    remove_state('kafka.started')
    hookenv.status_set('waiting', 'Waiting for Zookeeper to become ready')


@when('client.joined', 'zookeeper.ready')
def serve_client(client, zookeeper):
    kafka_port = DistConfig().port('kafka')
    client.send_port(kafka_port)
    client.send_zookeepers(zookeeper.zookeepers())
    hookenv.log('Sent Kafka configuration to client')
