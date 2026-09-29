package com.neo.controller;

import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HelloWorldController {

    @RequestMapping("/")
    public String index() {
        return "Spring Boot Hello\n";
    }
	
    @RequestMapping("/hello")
    public String hello() {
        return "Hello World";
    }
	
    @RequestMapping("/version")
    public String version() {
        return "version v1.2\n";
    }
}
