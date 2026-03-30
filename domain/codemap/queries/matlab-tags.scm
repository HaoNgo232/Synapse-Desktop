; Derived from Aider (based on nvim-treesitter tags) with Synapse Semantic customisations
; 

(class_definition
  name: (identifier) @name.definition.class) @definition.class

(function_definition
  name: (identifier) @name.definition.function) @definition.function

(function_call
  name: (identifier) @name.reference.call) @reference.call

(command (command_name) @name.reference.call) @reference.call