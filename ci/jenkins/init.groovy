import jenkins.model.Jenkins
import hudson.model.Node
import hudson.security.HudsonPrivateSecurityRealm
import hudson.security.FullControlOnceLoggedInAuthorizationStrategy
import hudson.slaves.DumbSlave
import hudson.slaves.JNLPLauncher
import hudson.slaves.RetentionStrategy
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition

def instance = Jenkins.get()
instance.setNumExecutors(0)
def realm = new HudsonPrivateSecurityRealm(false)
realm.createAccount('showcase-admin', System.getenv('SHOWCASE_JENKINS_PASSWORD'))
instance.setSecurityRealm(realm)
def strategy = new FullControlOnceLoggedInAuthorizationStrategy()
strategy.setAllowAnonymousRead(false)
instance.setAuthorizationStrategy(strategy)
instance.setSlaveAgentPort(-1) // WebSocket inbound agent only; no public agent listener.
if (instance.getNode('showcase-agent') == null) {
  instance.addNode(new DumbSlave('showcase-agent', 'Isolated local G1 agent', '/home/jenkins/agent', '1', Node.Mode.EXCLUSIVE, 'showcase-agent', new JNLPLauncher(), new RetentionStrategy.Always(), []))
}
def job = instance.getItem('g1') ?: instance.createProject(WorkflowJob, 'g1')
job.setDefinition(new CpsFlowDefinition(new File('/snapshot/Jenkinsfile').text, true))
job.save()
instance.save()
