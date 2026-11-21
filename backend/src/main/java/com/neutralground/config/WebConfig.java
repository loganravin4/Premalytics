package com.neutralground.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.filter.ShallowEtagHeaderFilter;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/** CORS from configuration (never a wildcard) and ETags on API responses. */
@Configuration
@EnableConfigurationProperties(NeutralGroundProperties.class)
public class WebConfig implements WebMvcConfigurer {

    private final NeutralGroundProperties properties;

    public WebConfig(NeutralGroundProperties properties) {
        this.properties = properties;
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins(properties.cors().allowedOrigins().stream()
                        .map(String::trim)
                        .filter(origin -> !origin.isEmpty() && !origin.equals("*"))
                        .toArray(String[]::new))
                .allowedMethods("GET", "POST", "OPTIONS")
                .allowedHeaders("Content-Type", "If-None-Match")
                .exposedHeaders("ETag", "Retry-After")
                .maxAge(3600);
    }

    @Bean
    public FilterRegistrationBean<ShallowEtagHeaderFilter> etagFilter() {
        FilterRegistrationBean<ShallowEtagHeaderFilter> registration =
                new FilterRegistrationBean<>(new ShallowEtagHeaderFilter());
        registration.addUrlPatterns("/api/*");
        registration.setName("etagFilter");
        return registration;
    }
}
