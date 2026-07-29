package com.interview.mysqlescdc.verifier.rebuild;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.web.server.ResponseStatusException;

class RebuildControllerTest {
    @Test void loopback_start_uses_coordinator_contract() {
        FakeStore store=new FakeStore();
        var coordinator=new RebuildCoordinator(store,new NoopWorkflow(),new RebuildFailpointRegistry(true));
        var controller=new RebuildController(coordinator,new RebuildFailpointRegistry(true),null);
        UUID run=UUID.randomUUID();
        MockHttpServletRequest request=loopback("127.0.0.1");
        var response=controller.start(new RebuildController.Start(run,"MYSQL_BINLOG_GAP",null,null),request);
        assertThat(response.getBody().status()).isEqualTo("CANAL_RECOVERY_REQUIRED");
        assertThat(store.request).isEqualTo(new RebuildRequest(run,"MYSQL_BINLOG_GAP","product-search-revisions",200));
    }

    @Test void non_loopback_cannot_operate_internal_rebuild_api() {
        var controller=new RebuildController(null,new RebuildFailpointRegistry(true),null);
        assertThatThrownBy(()->controller.status(UUID.randomUUID(),loopback("192.0.2.10")))
                .isInstanceOf(ResponseStatusException.class).hasMessageContaining("403");
    }

    @Test void failpoints_are_rejected_when_lab_mode_is_disabled() {
        var controller=new RebuildController(null,new RebuildFailpointRegistry(false),null);
        assertThatThrownBy(()->controller.failpoint(RebuildFailpoint.BEFORE_ALIAS_SWITCH,loopback("::1")))
                .isInstanceOf(IllegalStateException.class).hasMessageContaining("disabled");
    }

    private static MockHttpServletRequest loopback(String address){var request=new MockHttpServletRequest();request.setRemoteAddr(address);return request;}
    private static final class FakeStore implements RebuildRunStore{RebuildRequest request;String status;public void create(RebuildRequest r){request=r;status="CREATED";}public void transition(UUID r,String expected,String next){assertThat(status).isEqualTo(expected);status=next;}public void fail(UUID r,Throwable t){status="FAILED";}public RebuildStatus get(UUID r){return new RebuildStatus(r,status,"generation",null,false);}}
    private static final class NoopWorkflow implements RebuildCoordinator.Workflow{public void captureStart(UUID r){}public void createGeneration(UUID r){}public void openSnapshot(UUID r){}public void startShadow(UUID r){}public void scanSnapshot(UUID r){}public void closeSnapshot(UUID r){}public void assertRetained(UUID r){}public void closeGate(UUID r){}public void publishBarrier(UUID r){}public void observeBarrier(UUID r){}public void awaitPrimary(UUID r){}public void awaitShadow(UUID r){}public void pausePrimary(UUID r){}public void verifyPhysical(UUID r){}public void requireEligible(UUID r){}public void cutover(UUID r){}public void stopShadow(UUID r){}public void resumePrimary(UUID r){}public void clearLogGap(UUID r){}public void openGate(UUID r){}}
}
