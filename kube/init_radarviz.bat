@ECHO OFF

ECHO Initialize minikube

minikube start --mount-string "D:\:/mnt/data" --mount=true
@REM minikube start

kubectl apply -f redis-server.yaml
kubectl expose deployment/redis-server

START "" minikube mount "D:\:/mnt/data"

kubectl apply -f radarviz-server.yaml
kubectl expose deployment/radarviz-server

START "" kubectl port-forward --address 0.0.0.0 deployment/radarviz-server 8000:8000
@REM START "" kubectl port-forward deployment/radarviz-server 8000:8000

@REM minikube image load radarviz.tar
@REM minikube stop
@REM minikube ssh
@REM kubectl exec --stdin --tty radarviz -- /bin/bash
