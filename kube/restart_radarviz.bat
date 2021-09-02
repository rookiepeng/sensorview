@ECHO OFF

ECHO Initialize minikube

@REM minikube stop
@REM minikube start --mount-string "D:\:/mnt/data" --mount=true
@REM minikube start

START "" minikube mount "D:\:/mnt/data"

timeout 5
kubectl delete deployment/radarviz-server
kubectl delete services/radarviz-server
timeout 3
kubectl apply -f radarviz-server.yaml
kubectl expose deployment/radarviz-server

START "" kubectl port-forward --address 0.0.0.0 deployment/radarviz-server 8000:8000
@REM START "" kubectl port-forward deployment/radarviz-server 8000:8000
