declare const userInput: string;
declare const child_process: {
  exec(command: string): void;
  execSync(command: string): void;
};

eval(userInput);
child_process.exec(userInput);
