"""For increased readablitiy the problems of the scenarios are stored in this file."""

NGINX_WRONG_IMAGE = """my pod is not working, here is what kubectl returns:
apiVersion: v1
items:
- apiVersion: v1
kind: Pod
metadata:
    labels:
        run: mypod
    name: mypod
    namespace: myns
spec:
    containers:
        - image: ngix
        imagePullPolicy: Always
        name: mypod
        resources: {}
        terminationMessagePath: /dev/termination-log
        terminationMessagePolicy: File
        volumeMounts:
            - mountPath: /var/run/secrets/kubernetes.io/serviceaccount
            name: kube-api-access-xkmqb
            readOnly: true
    dnsPolicy: ClusterFirst
    enableServiceLinks: true
    nodeName: k3d-k3s-default-server-0
    preemptionPolicy: PreemptLowerPriority
    priority: 0
    restartPolicy: Always
    schedulerName: default-scheduler
    securityContext: {}
    serviceAccount: default
    serviceAccountName: default
    terminationGracePeriodSeconds: 30
    tolerations:
        - effect: NoExecute
        key: node.kubernetes.io/not-ready
        operator: Exists
        tolerationSeconds: 300
        - effect: NoExecute
        key: node.kubernetes.io/unreachable
        operator: Exists
        tolerationSeconds: 300
    volumes:
    - name: kube-api-access-xkmqb
    projected:
        defaultMode: 420
        sources:
        - serviceAccountToken:
            expirationSeconds: 3607
            path: token
        - configMap:
            items:
            - key: ca.crt
            path: ca.crt
            name: kube-root-ca.crt
        - downwardAPI:
            items:
            - fieldRef:
                apiVersion: v1
                fieldPath: metadata.namespace
            path: namespace
status:
    conditions:
        - lastProbeTime: null
        lastTransitionTime: "2024-05-27T11:42:02Z"
        status: "True"
        type: Initialized
        - lastProbeTime: null
        lastTransitionTime: "2024-05-27T11:42:02Z"
        message: 'containers with unready status: [mypod]'
        reason: ContainersNotReady
        status: "False"
        type: Ready
        - lastProbeTime: null
        lastTransitionTime: "2024-05-27T11:42:02Z"
        message: 'containers with unready status: [mypod]'
        reason: ContainersNotReady
        status: "False"
        type: ContainersReady
        - lastProbeTime: null
        lastTransitionTime: "2024-05-27T11:42:02Z"
        status: "True"
        type: PodScheduled
    containerStatuses:
        - image: ngix
        imageID: ""
        lastState: {}
        name: mypod
        ready: false
        restartCount: 0
        started: false
        state:
            waiting:
                message: Back-off pulling image "ngix"
                reason: ImagePullBackOff
    hostIP: 172.18.0.3
    phase: Pending
    podIP: 10.42.0.9
    podIPs:
        - ip: 10.42.0.9
    qosClass: BestEffort
    startTime: "2024-05-27T11:42:02Z"
kind: List
metadata:
    resourceVersion: ""
"""

WHOAMI_WRONG_QUOTA = """my application does not work, here is what kubectl returns:
apiVersion: v1
items:
- apiVersion: v1
  kind: Service
  metadata:
    creationTimestamp: "2023-10-10T18:03:35Z"
    name: whoami
    namespace: whoami
    resourceVersion: "50191305"
    uid: 468d7efd-56d1-439f-a23a-0219eb796b23
  spec:
    clusterIP: 10.111.192.151
    clusterIPs:
    - 10.111.192.151
    internalTrafficPolicy: Cluster
    ipFamilies:
    - IPv4
    ipFamilyPolicy: SingleStack
    ports:
    - port: 80
      protocol: TCP
      targetPort: 80
    selector:
      app: whoami
    sessionAffinity: None
    type: ClusterIP
  status:
    loadBalancer: {}
- apiVersion: apps/v1
  kind: Deployment
  metadata:
    annotations:
      deployment.kubernetes.io/revision: "1"
    creationTimestamp: "2023-10-10T18:03:35Z"
    generation: 1
    labels:
      app.kubernetes.io/name: whoami
    name: whoami
    namespace: whoami
    resourceVersion: "50191303"
    uid: e8592585-0677-46c2-982c-690215683271
  spec:
    progressDeadlineSeconds: 600
    replicas: 1
    revisionHistoryLimit: 10
    selector:
      matchLabels:
        app: whoami
    strategy:
      rollingUpdate:
        maxSurge: 25%
        maxUnavailable: 25%
      type: RollingUpdate
    template:
      metadata:
        creationTimestamp: null
        labels:
          app: whoami
          sidecar.istio.io/inject: "false"
      spec:
        containers:
        - image: traefik/whoami:latest
          imagePullPolicy: Always
          livenessProbe:
            failureThreshold: 3
            httpGet:
              path: /health
              port: 80
              scheme: HTTP
            initialDelaySeconds: 30
            periodSeconds: 10
            successThreshold: 1
            timeoutSeconds: 30
          name: whoami
          ports:
          - containerPort: 80
            protocol: TCP
          resources:
            limits:
              cpu: 250m
              memory: 32Mi
            requests:
              cpu: 100m
              memory: 24Mi
          terminationMessagePath: /dev/termination-log
          terminationMessagePolicy: File
        dnsPolicy: ClusterFirst
        restartPolicy: Always
        schedulerName: default-scheduler
        securityContext: {}
        terminationGracePeriodSeconds: 30
  status:
    conditions:
    - lastTransitionTime: "2023-10-10T18:03:35Z"
      lastUpdateTime: "2023-10-10T18:03:35Z"
      message: Created new replica set "whoami-56dbdb4756"
      reason: NewReplicaSetCreated
      status: "True"
      type: Progressing
    - lastTransitionTime: "2023-10-10T18:03:35Z"
      lastUpdateTime: "2023-10-10T18:03:35Z"
      message: Deployment does not have minimum availability.
      reason: MinimumReplicasUnavailable
      status: "False"
      type: Available
    - lastTransitionTime: "2023-10-10T18:03:35Z"
      lastUpdateTime: "2023-10-10T18:03:35Z"
      message: 'pods "whoami-56dbdb4756-g57bl" is forbidden: exceeded quota: whoami-resource-quota,
        requested: limits.cpu=250m,requests.cpu=100m, used: limits.cpu=0,requests.cpu=0,
        limited: limits.cpu=50m,requests.cpu=25m'
      reason: FailedCreate
      status: "True"
      type: ReplicaFailure
    observedGeneration: 1
    unavailableReplicas: 1
- apiVersion: apps/v1
  kind: ReplicaSet
  metadata:
    annotations:
      deployment.kubernetes.io/desired-replicas: "1"
      deployment.kubernetes.io/max-replicas: "2"
      deployment.kubernetes.io/revision: "1"
    creationTimestamp: "2023-10-10T18:03:35Z"
    generation: 1
    labels:
      app: whoami
      pod-template-hash: 56dbdb4756
      sidecar.istio.io/inject: "false"
    name: whoami-56dbdb4756
    namespace: whoami
    ownerReferences:
    - apiVersion: apps/v1
      blockOwnerDeletion: true
      controller: true
      kind: Deployment
      name: whoami
      uid: e8592585-0677-46c2-982c-690215683271
    resourceVersion: "50191301"
    uid: e59b9b2f-91a6-4a0a-b9f7-b6f8fc2faadb
  spec:
    replicas: 1
    selector:
      matchLabels:
        app: whoami
        pod-template-hash: 56dbdb4756
    template:
      metadata:
        creationTimestamp: null
        labels:
          app: whoami
          pod-template-hash: 56dbdb4756
          sidecar.istio.io/inject: "false"
      spec:
        containers:
        - image: traefik/whoami:latest
          imagePullPolicy: Always
          livenessProbe:
            failureThreshold: 3
            httpGet:
              path: /health
              port: 80
              scheme: HTTP
            initialDelaySeconds: 30
            periodSeconds: 10
            successThreshold: 1
            timeoutSeconds: 30
          name: whoami
          ports:
          - containerPort: 80
            protocol: TCP
          resources:
            limits:
              cpu: 250m
              memory: 32Mi
            requests:
              cpu: 100m
              memory: 24Mi
          terminationMessagePath: /dev/termination-log
          terminationMessagePolicy: File
        dnsPolicy: ClusterFirst
        restartPolicy: Always
        schedulerName: default-scheduler
        securityContext: {}
        terminationGracePeriodSeconds: 30
  status:
    conditions:
    - lastTransitionTime: "2023-10-10T18:03:35Z"
      message: 'pods "whoami-56dbdb4756-g57bl" is forbidden: exceeded quota: whoami-resource-quota,
        requested: limits.cpu=250m,requests.cpu=100m, used: limits.cpu=0,requests.cpu=0,
        limited: limits.cpu=50m,requests.cpu=25m'
      reason: FailedCreate
      status: "True"
      type: ReplicaFailure
    observedGeneration: 1
    replicas: 0
- apiVersion: autoscaling/v2
  kind: HorizontalPodAutoscaler
  metadata:
    annotations:
      kubectl.kubernetes.io/last-applied-configuration: |
        {"apiVersion":"autoscaling/v2","kind":"HorizontalPodAutoscaler","metadata":{"annotations":{},"labels":{"app":"whoami"},"name":"whoami","namespace":"whoami-wrong-quota"},"spec":{"maxReplicas":4,"metrics":[{"resource":{"name":"cpu","target":{"averageUtilization":80,"type":"Utilization"}},"type":"Resource"}],"minReplicas":1,"scaleTargetRef":{"apiVersion":"apps/v1","kind":"Deployment","name":"whoami"}}}
    creationTimestamp: "2023-10-10T18:03:35Z"
    labels:
      app: whoami
    name: whoami
    namespace: whoami
    resourceVersion: "50191634"
    uid: 1350f545-48d6-4d05-bbb5-6d8ff51d5ec8
  spec:
    maxReplicas: 4
    metrics:
    - resource:
        name: cpu
        target:
          averageUtilization: 80
          type: Utilization
      type: Resource
    minReplicas: 1
    scaleTargetRef:
      apiVersion: apps/v1
      kind: Deployment
      name: whoami
  status:
    conditions:
    - lastTransitionTime: "2023-10-10T18:04:05Z"
      message: the HPA controller was able to get the target's current scale
      reason: SucceededGetScale
      status: "True"
      type: AbleToScale
    - lastTransitionTime: "2023-10-10T18:04:05Z"
      message: 'the HPA was unable to compute the replica count: failed to get cpu
        utilization: unable to get metrics for resource cpu: no metrics returned from
        resource metrics API'
      reason: FailedGetResourceMetric
      status: "False"
      type: ScalingActive
    currentMetrics: null
    currentReplicas: 1
    desiredReplicas: 0
kind: List
metadata:
  resourceVersion: ""
apiVersion: v1
items:
- apiVersion: v1
  kind: ResourceQuota
  metadata:
    creationTimestamp: "2024-06-10T18:03:35Z"
    name: whoami-resource-quota
    namespace: whoami
    resourceVersion: "50191294"
    uid: eca03fb8-b292-459b-80b6-039929c8ecbe
  spec:
    hard:
      limits.cpu: 50m
      limits.memory: 128Mi
      requests.cpu: 25m
      requests.memory: 96Mi
  status:
    hard:
      limits.cpu: 50m
      limits.memory: 128Mi
      requests.cpu: 25m
      requests.memory: 96Mi
    used:
      limits.cpu: "0"
      limits.memory: "0"
      requests.cpu: "0"
      requests.memory: "0"
kind: List
metadata:
  resourceVersion: ""
"""

KYMA_APP_SYNTAX_ERROR = """I have a problem with my kubernetes application, here is what kubectl returns:
apiVersion: serverless.kyma-project.io/v1alpha2
kind: Function
metadata:
  annotations:
    kubectl.kubernetes.io/last-applied-configuration: |
      {"apiVersion":"serverless.kyma-project.io/v1alpha2","kind":"Function","metadata":{"annotations":{},"labels":{"app":"restapi"},"name":"func1","namespace":"kyma-app-no-function"},"spec":{"runtime":"nodejs20","source":{"inline":{"dependencies":"{ \n  \"name\": \"func1\",\n  \"version\": \"1.0.0\",\n  \"dependencies\": {}\n}","source":"module.exports = {\n  main: async function (event, context) {\n      // Return a response.\n      const now = new Dates();\n      const response = {\n      statusCode: 200,\n      result: {\n        message: 'Serverless function is up and running',\n        status: 'success',\n        utcDatetime: now\n      }\n    };\n    console.log('Response:', response);\n    return response;\n  } \n}\n"}}}}
  creationTimestamp: "2024-06-10T18:44:20Z"
  generation: 1
  labels:
    app: restapi
  name: func1
  namespace: kyma-app-no-function
  resourceVersion: "50222394"
  uid: 392cec36-4cac-497f-b300-c81526955870
spec:
  replicas: 1
  runtime: nodejs20
  source:
    inline:
      dependencies: |-
        { 
          "name": "func1",
          "version": "1.0.0",
          "dependencies": {}
        }
      source: |
        module.exports = {
          main: async function (event, context) {
              // Return a response.
              const now = new Dates();
              const response = {
              statusCode: 200,
              result: {
                message: 'Serverless function is up and running',
                status: 'success',
                utcDatetime: now
              }
            };
            console.log('Response:', response);
            return response;
          } 
        }
status:
  buildResourceProfile: normal
  conditions:
  - lastTransitionTime: "2024-06-10T18:49:45Z"
    message: Deployment func1-x4f4q is ready
    reason: DeploymentReady
    status: "True"
    type: Running
  - lastTransitionTime: "2024-06-10T18:44:33Z"
    message: Job func1-build-z8b8l finished
    reason: JobFinished
    status: "True"
    type: BuildReady
  - lastTransitionTime: "2024-06-10T18:44:20Z"
    message: ConfigMap func1-5dpvv created
    reason: ConfigMapCreated
    status: "True"
    type: ConfigurationReady
  functionResourceProfile: L
  podSelector: serverless.kyma-project.io/function-name=func1,serverless.kyma-project.io/managed-by=function-controller,serverless.kyma-project.io/resource=deployment,serverless.kyma-project.io/uuid=392cec36-4cac-497f-b300-c81526955870
  replicas: 1
  runtime: nodejs20
  runtimeImage: europe-docker.pkg.dev/kyma-project/prod/function-runtime-nodejs20:1.5.0
"""

KYMA_APP_WRONG_LANGUAGE = """I have a problem with my kubernetes application, here is what kubectl returns:
apiVersion: serverless.kyma-project.io/v1alpha2
kind: Function
metadata:
  annotations:
    kubectl.kubernetes.io/last-applied-configuration: |
      {"apiVersion":"serverless.kyma-project.io/v1alpha2","kind":"Function","metadata":{"annotations":{},"labels":{"app":"restapi"},"name":"func1","namespace":"kyma-app-wrong-lang"},"spec":{"runtime":"python312","source":{"inline":{"dependencies":"{ \n  \"name\": \"func1\",\n  \"version\": \"1.0.0\",\n  \"dependencies\": {}\n}","source":"module.exports = {\n  main: async function (event, context) {\n      // Return a response.\n      const now = new Date();\n      const response = {\n      statusCode: 200,\n      result: {\n        message: 'Serverless function is up and running',\n        status: 'success',\n        utcDatetime: now\n      }\n    };\n    console.log('Response:', response);\n    return response;\n  } \n}\n"}}}}
  creationTimestamp: "2024-06-10T19:18:47Z"
  generation: 1
  labels:
    app: restapi
  name: func1
  namespace: kyma-app-wrong-lang
  resourceVersion: "50241810"
  uid: 3b6da2d8-326e-4de1-8ed5-88ffbe305551
spec:
  replicas: 1
  runtime: python312
  source:
    inline:
      dependencies: |-
        { 
          "name": "func1",
          "version": "1.0.0",
          "dependencies": {}
        }
      source: |
        module.exports = {
          main: async function (event, context) {
              // Return a response.
              const now = new Date();
              const response = {
              statusCode: 200,
              result: {
                message: 'Serverless function is up and running',
                status: 'success',
                utcDatetime: now
              }
            };
            console.log('Response:', response);
            return response;
          } 
        }
status:
  buildResourceProfile: normal
  conditions:
  - lastTransitionTime: "2024-06-10T19:19:02Z"
    message: Job func1-build-snxd4 failed, it will be re-run
    reason: JobFailed
    status: "False"
    type: BuildReady
  - lastTransitionTime: "2024-06-10T19:18:48Z"
    message: ConfigMap func1-zf9v6 created
    reason: ConfigMapCreated
    status: "True"
    type: ConfigurationReady
  functionResourceProfile: L
  podSelector: serverless.kyma-project.io/function-name=func1,serverless.kyma-project.io/managed-by=function-controller,serverless.kyma-project.io/resource=deployment,serverless.kyma-project.io/uuid=3b6da2d8-326e-4de1-8ed5-88ffbe305551
  runtime: python312
  runtimeImage: europe-docker.pkg.dev/kyma-project/prod/function-runtime-python312:1.5.0
"""
