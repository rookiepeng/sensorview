@ECHO OFF

ECHO Initialize minikube

@REM minikube start --mount-string "D:\:/mnt/data" --mount=true
minikube start

kubectl apply -f redis-server.yaml
kubectl expose deployment/redis-server

START "" minikube mount "D:\:/mnt/data"

@REM minikube mount "C:\Users\zjx8rj\OneDrive - Aptiv\Road_Data:/mnt/data"

@REM minikube image load sensorview.tar
kubectl apply -f sensorview-server.yaml
kubectl expose deployment/sensorview-server

@REM START "" kubectl port-forward --address 0.0.0.0 deployment/sensorview-server 8000:8000
START "" kubectl port-forward --address 127.0.0.1 deployment/sensorview-server 8000:8000

kubectl port-forward --address 127.0.0.1 deployment/sensorview-server 6379:6379

@REM minikube image load sensorview.tar
@REM minikube stop
@REM minikube ssh
@REM kubectl exec --stdin --tty sensorview -- /bin/bash