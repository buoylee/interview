package com.interview.mysqlescdc.verifier.rebuild;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.UUID;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

class RebuildControllerTest {
    @Test void loopback_start_uses_coordinator_contract() {
        FakeStore store=new FakeStore();
        var coordinator=new RebuildCoordinator(store,new NoopWorkflow(),new RebuildFailpointRegistry(true));
        var controller=new RebuildController(coordinator,new RebuildFailpointRegistry(true),null,null,false);
        UUID run=UUID.randomUUID();
        var response=controller.start(new RebuildController.Start(run,"MYSQL_BINLOG_GAP","product-search-revisions",200),loopback("127.0.0.1"));
        assertThat(response.getBody().status()).isEqualTo("CANAL_RECOVERY_REQUIRED");
        assertThat(store.request).isEqualTo(new RebuildRequest(run,"MYSQL_BINLOG_GAP","product-search-revisions",200));
    }

    @Test void loopback_start_preserves_a_small_page_size_for_fault_evidence() {
        FakeStore store=new FakeStore();
        var coordinator=new RebuildCoordinator(store,new NoopWorkflow(),new RebuildFailpointRegistry(true));
        var controller=new RebuildController(coordinator,new RebuildFailpointRegistry(true),null,null,false);
        UUID run=UUID.randomUUID();

        controller.start(new RebuildController.Start(run,"NORMAL","product-search-revisions",10),loopback("127.0.0.1"));

        assertThat(store.request.pageSize()).isEqualTo(10);
    }

    @Test void non_loopback_cannot_operate_internal_rebuild_api() {
        var controller=new RebuildController(null,new RebuildFailpointRegistry(true),null,null,false);
        assertThatThrownBy(()->controller.status(UUID.randomUUID(),loopback("192.0.2.10")))
                .isInstanceOf(ResponseStatusException.class).hasMessageContaining("403");
    }

    @Test void both_failpoint_mutations_are_rejected_when_lab_mode_is_disabled() {
        var controller=new RebuildController(null,new RebuildFailpointRegistry(false),null,null,false);
        assertThatThrownBy(()->controller.failpoint(RebuildFailpoint.BEFORE_ALIAS_SWITCH,loopback("::1")))
                .isInstanceOf(IllegalStateException.class).hasMessageContaining("disabled");
        assertThatThrownBy(()->controller.clear(loopback("::1")))
                .isInstanceOf(IllegalStateException.class).hasMessageContaining("disabled");
    }

    @ParameterizedTest @MethodSource("invalidStarts")
    void invalid_v1_contract_is_rejected_before_persistence_or_side_effects(RebuildController.Start invalid) {
        FakeStore store=new FakeStore();NoopWorkflow workflow=new NoopWorkflow();
        var controller=new RebuildController(new RebuildCoordinator(store,workflow,new RebuildFailpointRegistry(true)),new RebuildFailpointRegistry(true),null,null,false);
        assertThatThrownBy(()->controller.start(invalid,loopback("127.0.0.1"))).isInstanceOf(IllegalArgumentException.class);
        assertThat(store.createCalls).isZero();assertThat(workflow.calls).isZero();
    }

    @Test void invalid_contract_is_exposed_as_bounded_http_400() {
        var response=new RebuildApiExceptionHandler().invalid(new IllegalArgumentException("bad request"));
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(response.getBody()).containsEntry("code","REBUILD_REJECTED").containsEntry("message","bad request");
    }

    @Test void docker_bridge_address_is_accepted_only_by_explicit_lab_switch() {
        var denied=new RebuildController(null,new RebuildFailpointRegistry(true),null,null,false);
        assertThatThrownBy(()->denied.status(UUID.randomUUID(),loopback("172.18.0.1"))).isInstanceOf(ResponseStatusException.class);
        FakeStore store=new FakeStore();store.status="COMPLETED";
        var allowed=new RebuildController(new RebuildCoordinator(store,new NoopWorkflow(),new RebuildFailpointRegistry(true)),new RebuildFailpointRegistry(true),null,null,true);
        assertThat(allowed.status(UUID.randomUUID(),loopback("172.18.0.1")).status()).isEqualTo("COMPLETED");
    }

    static Stream<RebuildController.Start> invalidStarts(){UUID run=UUID.randomUUID();return Stream.of(
            new RebuildController.Start(null,"NORMAL","product-search-revisions",200),
            new RebuildController.Start(run,null,"product-search-revisions",200),
            new RebuildController.Start(run,"","product-search-revisions",200),
            new RebuildController.Start(run,"OTHER","product-search-revisions",200),
            new RebuildController.Start(run,"NORMAL",null,200),
            new RebuildController.Start(run,"NORMAL","",200),
            new RebuildController.Start(run,"NORMAL","other-topic",200),
            new RebuildController.Start(run,"NORMAL","product-search-revisions",0),
            new RebuildController.Start(run,"NORMAL","product-search-revisions",-1),
            new RebuildController.Start(run,"NORMAL","product-search-revisions",1001));}

    private static MockHttpServletRequest loopback(String address){var request=new MockHttpServletRequest();request.setRemoteAddr(address);return request;}
    private static final class FakeStore implements RebuildRunStore{RebuildRequest request;String status;int createCalls;public void create(RebuildRequest r){createCalls++;request=r;status="CREATED";}public void transition(UUID r,String expected,String next){assertThat(status).isEqualTo(expected);status=next;}public void fail(UUID r,Throwable t){status="FAILED";}public RebuildStatus get(UUID r){return new RebuildStatus(r,status,"generation",null,false);}}
    private static final class NoopWorkflow implements RebuildCoordinator.Workflow{int calls;private void call(){calls++;}public void captureStart(UUID r){call();}public void createGeneration(UUID r){call();}public void openSnapshot(UUID r){call();}public void startShadow(UUID r){call();}public void scanSnapshot(UUID r){call();}public void closeSnapshot(UUID r){call();}public void assertRetained(UUID r){call();}public void closeGate(UUID r){call();}public void publishBarrier(UUID r){call();}public void observeBarrier(UUID r){call();}public void awaitPrimary(UUID r){call();}public void awaitShadow(UUID r){call();}public void pausePrimary(UUID r){call();}public void verifyPhysical(UUID r){call();}public void requireEligible(UUID r){call();}public void cutover(UUID r){call();}public void stopShadow(UUID r){call();}public void resumePrimary(UUID r){call();}public void clearLogGap(UUID r){call();}public void openGate(UUID r){call();}}
}
