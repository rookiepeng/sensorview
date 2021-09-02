@ECHO OFF

ECHO Initialize minikube

@REM minikube stop
@REM minikube start --mount-string "D:\:/mnt/data" --mount=true
@REM minikube start

START "" minikube mount "D:\:/mnt/data"

timeout 5
kubectl delete deployment/sensorview-server
kubectl delete services/sensorview-server
timeout 3
kubectl apply -f sensorview-server.yaml
kubectl expose deployment/sensorview-server

@REM START "" kubectl port-forward --address 0.0.0.0 deployment/sensorview-server 8000:8000
START "" kubectl port-forward deployment/sensorview-server 8000:8000