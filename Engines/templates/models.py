MODEL_DOC_TEMPLATE = '''{frontmatter}

{title}

{uuid}

{criticality}

{tlp}


{techniques}

{expand_header}

---

`{metadata}`


## 👁️ Description

> {description}

{expand_description}

---

## ⛓️ Relations

{relation_graph}

{relation_table}

{expand_graphs}

---

## Model Data

{data_table}


## 🔗 References

{references}

---

#### 🏷️ Tags

{tags}

'''

VOCABS_DOC_TEMPLATE ='''

{title}

`{field}`

{stages}

> {vocab_description}

{table}

'''
