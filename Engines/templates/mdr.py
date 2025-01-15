########
# Managed Detection Rules Template
########


TEMPLATEv3 = '''{frontmatter}

{name}

{tlp}

{techniques}

---

{metadata}

## 👁️‍🗨️ Description

> {description}

### 🕸️ Relations

{cdm}

&nbsp;

## ⚠️ Response

{response}

&nbsp;

## 💽 Configurations

{configurations}

### 🔎 Queries

{queries}


{references}

&nbsp;


'''

TEMPLATEv2 = '''{frontmatter}

{title}

{uuid}

{status}

{priority}

{tlp}

{techniques}

---

## 💽 Description
> {description}
{falsepositives}

### 👣 Playbook

{playbook}

### ‍🚒 Alert Handling Team

{responders}

### 🛡️ Detection Model
{detectionmodel}

### ⚒️ Parameters

{scheduling}

{timeframe}

{throttling}

{threshold}

{logsources}

{fields}

---
## ⚗️ Detections 
{rules}

### 🔗 References

{references}

`{meta}`

'''