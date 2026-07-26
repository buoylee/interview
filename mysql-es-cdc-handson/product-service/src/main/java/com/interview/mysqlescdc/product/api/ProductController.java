package com.interview.mysqlescdc.product.api;

import jakarta.validation.Valid;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.interview.mysqlescdc.product.api.ProductRequests.ChangePriceRequest;
import com.interview.mysqlescdc.product.api.ProductRequests.CreateProductRequest;
import com.interview.mysqlescdc.product.api.ProductRequests.RenameCategoryRequest;
import com.interview.mysqlescdc.product.api.ProductRequests.ReplaceInventoryRequest;
import com.interview.mysqlescdc.product.api.ProductRequests.RevisionResponse;
import com.interview.mysqlescdc.product.application.ProductMutationService;

@RestController
@RequestMapping("/api")
public class ProductController {
    private final ProductMutationService service;

    public ProductController(ProductMutationService service) {
        this.service = service;
    }

    @PostMapping("/products")
    @ResponseStatus(HttpStatus.CREATED)
    RevisionResponse create(@Valid @RequestBody CreateProductRequest request) {
        return new RevisionResponse(request.id(), service.createProduct(request));
    }

    @PutMapping("/products/{id}/price")
    RevisionResponse changePrice(@PathVariable long id,
                                 @Valid @RequestBody ChangePriceRequest request) {
        return new RevisionResponse(id, service.changePrice(id, request.priceCents()));
    }

    @PutMapping("/products/{id}/inventory")
    RevisionResponse replaceInventory(@PathVariable long id,
                                      @Valid @RequestBody ReplaceInventoryRequest request) {
        return new RevisionResponse(id, service.replaceInventory(
                id, request.availableQuantity(), request.reservedQuantity()));
    }

    @PutMapping("/categories/{id}")
    int renameCategory(@PathVariable long id,
                       @Valid @RequestBody RenameCategoryRequest request) {
        return service.renameCategory(id, request.name());
    }

    @DeleteMapping("/products/{id}")
    RevisionResponse delete(@PathVariable long id) {
        return new RevisionResponse(id, service.deleteProduct(id));
    }
}
