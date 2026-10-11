- Language: zh-TW
- Expected diagram type: `flowchart` with `subgraph` blocks (what contains what)

## Source

Kubernetes 用來管理很多台機器上的容器。最外層是叢集，叢集由一個控制平面和多個工作節點組成。控制平面負責決定每個應用程式要放在哪個節點上執行，並持續確認實際狀態和設定一致。工作節點是真正執行程式的機器，每個節點上可以跑多個 Pod。Pod 是 Kubernetes 管理的最小單位，一個 Pod 裡有一個或多個容器，同一個 Pod 裡的容器共用同一個網路位址，可以用 localhost 互相連線。Pod 可能隨時被重新建立，位址也會跟著改變，所以 Kubernetes 用 Service 提供一個固定的入口，把流量分給背後符合條件的多個 Pod。

## Reader should understand

- 叢集由控制平面和多個工作節點組成。
- 控制平面決定程式在哪個節點執行，工作節點負責實際執行。
- 每個節點上可以跑多個 Pod；一個 Pod 裡有一個或多個容器，共用同一個網路位址。
- Service 提供固定的入口，把流量分給背後的多個 Pod。

## Diagram hints

- Expected type: `flowchart` with nested `subgraph` blocks: 叢集 ⊃ 控制平面, 節點 1, 節點 2; each node ⊃ two Pods; one Pod ⊃ two containers.
- Key nodes (about 12): 控制平面, two 節點, four Pod, a few 容器, Service; edges from Service to the Pods it serves, and from 控制平面 to the nodes (排程).
- Color can tell kinds apart (control plane, node, Pod, Service) with a legend.
- The caption should point at the Service as the stable entry in front of changing Pods.
