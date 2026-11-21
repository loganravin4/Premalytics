package com.neutralground.web;

import com.neutralground.config.NeutralGroundProperties;
import org.springframework.core.MethodParameter;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.converter.HttpMessageConverter;
import org.springframework.http.server.ServerHttpRequest;
import org.springframework.http.server.ServerHttpResponse;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.servlet.mvc.method.annotation.ResponseBodyAdvice;

/** Short shared caching on GETs is safe because the data only changes when a model run is published. */
@ControllerAdvice(basePackages = "com.neutralground.web")
public class ReadCacheHeaders implements ResponseBodyAdvice<Object> {

    private final CacheControl cacheControl;

    public ReadCacheHeaders(NeutralGroundProperties properties) {
        this.cacheControl = CacheControl.maxAge(properties.readCache().maxAge()).cachePublic();
    }

    @Override
    public boolean supports(MethodParameter returnType, Class<? extends HttpMessageConverter<?>> converterType) {
        return true;
    }

    @Override
    public Object beforeBodyWrite(Object body, MethodParameter returnType, MediaType contentType,
                                  Class<? extends HttpMessageConverter<?>> converterType,
                                  ServerHttpRequest request, ServerHttpResponse response) {
        if (HttpMethod.GET.equals(request.getMethod()) && !(body instanceof ApiError)) {
            response.getHeaders().setCacheControl(cacheControl);
        } else {
            response.getHeaders().setCacheControl(CacheControl.noStore());
        }
        return body;
    }
}
