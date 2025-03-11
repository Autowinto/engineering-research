use std::env;
use std::fs;
use std::string;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        println!("Please enter a path!");
        return;
    }
    let path = &args[1];
    let file_string = fs::read_to_string(path).expect("Failed to read file with provided path");

    let json: serde_json::Value = 
        serde_json::from_str(&file_string).expect("JSON was not well-formatted");
    
}