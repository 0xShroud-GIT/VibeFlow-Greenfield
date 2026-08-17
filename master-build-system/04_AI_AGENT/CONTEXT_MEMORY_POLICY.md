# Context / Memory Policy

Every context item should be classifiable by source, project, task/execution, sensitivity and retention. Cross-project memory is opt-in/policy governed. Provider prompts must not contain raw SecretRef values unless a tool call explicitly requires a brokered secret at execution time. Evidence records what context class/revision was used without storing sensitive prompt payloads by default.
